import json
import os
import shutil
import subprocess
import time
import sys
import fileinput
import re

def read_configuration_template(configuration_template_file):
    # Read data in the config file into one string
    with open(configuration_template_file, 'r') as file:
        configuration_template = file.read()
    return configuration_template


def read_app_template(app_template_file):
    # Read data in the app file into one string
    with open(app_template_file, 'r') as file:
        app_template = file.read()
    return app_template


def read_network_template(network_template_file):
    # Create a dictionary with the attributes (such as PORT names) and values
    network_template = {}
    with open(network_template_file, 'r') as file:
        template = file.readlines()
        for line in template:
            line = line.strip() # Clean string, remove newlines etc.
            if len(line) == 0: # If line is empty, skip to next line
                continue
            data = line.split("=") # Split data into atribute and value
            network_template[data[0]] = data[1]
    return network_template


def make_replacements(template, port_sequence):
    configs = template
    # Replace default values in the template
    for item in network_template:
        if item.endswith("_PORT"): # If the item is a network port, use increments to avoid conflicting ports for different nodes
            configs = configs.replace("<" + item + ">", str(int(network_template[item]) + port_sequence))
        else:
            configs = configs.replace("<" + item + ">", network_template[item])
    return configs


def get_validator_pubkey(node_dir):
    val_pub_key = subprocess.check_output(['gaiad', 'tendermint', 'show-validator', '--home', node_dir.rstrip('/config')])
    val_pub_key = val_pub_key.decode("utf-8").rstrip('\n')
    return val_pub_key


def get_validator_id(node_dir):
    global local_sequence
    # subprocess.call(['gaiad', 'init', '--home', node_dir])
    nodeid = subprocess.check_output(['gaiad', 'tendermint', 'show-node-id', '--home', str(node_dir).rstrip("config/")])
    peer_id = str(nodeid.decode("utf-8").rstrip('\n') + '@' + network_template['P2P_PEERID_IP'] + ':' + str(int(network_template['P2P_LADDR_PORT']) + int(local_sequence)))
    local_sequence += 10
    return peer_id


#---------------------------------- MAIN BODY ----------------------------------------

if len(sys.argv) < 6:
    print("[+] Usage: python3 {} <CHAIN_ID> <NETWORK_DEFAULTS.txt> <NUMBER_OF_NODES> <NUMBER_OF_ACCOUNTS> [TIMEOUT_COMMIT]".format(sys.argv[0].lstrip("./")))
    raise SystemExit
    
chain_id = sys.argv[1] 
network_defaults = sys.argv[2] # File containing default network configuration
number_of_nodes = int(sys.argv[3]) # Number of nodes to add to the testnet
number_of_accounts = int(sys.argv[4])
init_accounts = sys.argv[5] # If it's the source chain, initialize user accounts for transfers


working_directory = os.getcwd() + "/" # Get current working directory
network_template_file = working_directory + 'templates/' + network_defaults  # Network configuration/ports template
configuration_template_file = working_directory + 'templates/tendermint_config.toml' # Tendermint configuration file
app_template_file = working_directory + 'templates/tendermint_app.toml' # Application configuration file
target_node_dir = working_directory + '/' + chain_id + '/node0/gaiad/config/'

node_directories = []
target_configs = []
target_apps = []

port_sequence = 0
port_increment = 10
local_sequence = 0

network_template = read_network_template(network_template_file)

configuration_template = read_configuration_template(configuration_template_file)

if len(sys.argv) == 7:
    try:
        tendermint_timeout_commit = int(sys.argv[6])
    except ValueError:
        print("Please use only integer values for timeout commit.")
        print("Using default value (10s)")
        tendermint_timeout_commit = "10"

    configuration_template = re.sub(r'timeout_commit = "\d+(s|ms)"', 'timeout_commit = "{}s"'.format(tendermint_timeout_commit), configuration_template) 


app_template = read_app_template(app_template_file)

# A genesis file that contains info to boostrap the blockchain from height 0 and will be replicated for every node
common_genesis = working_directory + network_template['replacement_genesis']


print("[+] Creating testnet subdirectories for chain '{}'...".format(chain_id))

# Removes chain data from previous runs (WARNING, may be used to remove other folders by inputing their name)
subprocess.call(['rm', '-rf', working_directory + chain_id]) 


# Creates directories for each node ($(pwd)/chain_0/node0/gaiad/config) and replace node0 with the node's name
for node_number in range(number_of_nodes):
    node_directories.append(target_node_dir.replace("node0", "node" + str(node_number))) # Create a list containing directory paths for every node that will be created

# Call the gaiad daemon to initialize a directory called 'mytestnet' by default. Contains 'number_of_nodes' directories, one for each node
subprocess.call(['gaiad', 'testnet', '--keyring-backend=test', '--v', str(number_of_nodes), '-o', chain_id, '--chain-id', chain_id], stdout=subprocess.DEVNULL,
    stderr=subprocess.STDOUT) # 

# Get the id of the validators for each one of the testnet nodes
peer_ids = [get_validator_id(node_dir) for node_dir in node_directories]

# Change peer addresses to the addresses of the remote machines

remote_machine_addresses = ["", "", "", "", ""]

for i in range(len(peer_ids)):
    peer_id = peer_ids[i].split("@")[0]
    machine_index = i % len(remote_machine_addresses)
    addr = remote_machine_addresses[machine_index]
    port = peer_ids[i].split(":")[1]
    peer_ids[i] = peer_id + "@" + addr + ":" + port

# Make the validator list into a string with the IDs separated by commas
peers = ",".join(peer_ids)
print("\n[+] Testnet peer IDs: " + peers)

# Replace 'SEEDS' attribute value in the configuration file with the list of validator IDs
main_configuration_template = configuration_template.replace("<SEEDS>", peers)

# Collect the public keys of each validator in the testnet chain
testnet_validator_pubkeys = [get_validator_pubkey(t) for t in node_directories]
print("\n[+] Testnet validator pubkeys: " + str(testnet_validator_pubkeys))

# Add user account with funds to node0 in order to be able to submit cross-chain transactions
node_dir = node_directories[0] # Directory for node0


# Add a key named "testkey" that will be used by hermes to open a channel between the IBC chains (the key used by the relayer is defined in the hermes_config.toml file)
subprocess.call(['gaiad --home {0} --keyring-backend=test keys add testkey_hermes0_chain0 --output json 2> {0}/testkey_hermes0_chain0_keys.json'.format(node_dir.rstrip('/config'))], shell=True)
subprocess.call(['gaiad --home {0} --keyring-backend=test add-genesis-account $(gaiad --home {0} --keyring-backend=test keys show testkey_hermes0_chain0 -a) 1000000000000000stake,10000000000coins'.format(node_dir.rstrip('/config'))], shell=True)

subprocess.call(['gaiad --home {0} --keyring-backend=test keys add testkey_hermes0_chain1 --output json 2> {0}/testkey_hermes0_chain1_keys.json'.format(node_dir.rstrip('/config'))], shell=True)
subprocess.call(['gaiad --home {0} --keyring-backend=test add-genesis-account $(gaiad --home {0} --keyring-backend=test keys show testkey_hermes0_chain1 -a) 1000000000000000stake,10000000000coins'.format(node_dir.rstrip('/config'))], shell=True)

subprocess.call(['gaiad --home {0} --keyring-backend=test keys add testkey_hermes1_chain0 --output json 2> {0}/testkey_hermes1_chain0_keys.json'.format(node_dir.rstrip('/config'))], shell=True)
subprocess.call(['gaiad --home {0} --keyring-backend=test add-genesis-account $(gaiad --home {0} --keyring-backend=test keys show testkey_hermes1_chain0 -a) 1000000000000000stake,10000000000coins'.format(node_dir.rstrip('/config'))], shell=True)

subprocess.call(['gaiad --home {0} --keyring-backend=test keys add testkey_hermes1_chain1 --output json 2> {0}/testkey_hermes1_chain1_keys.json'.format(node_dir.rstrip('/config'))], shell=True)
subprocess.call(['gaiad --home {0} --keyring-backend=test add-genesis-account $(gaiad --home {0} --keyring-backend=test keys show testkey_hermes1_chain1 -a) 1000000000000000stake,10000000000coins'.format(node_dir.rstrip('/config'))], shell=True)

if init_accounts == 'true':
    print("\n[+] Generating {} user accounts and keys...".format(number_of_accounts))
    for i in range(1, number_of_accounts + 1):
        subprocess.call(['gaiad --home {0} --keyring-backend=test keys add {1} --output json 2> {0}/{1}_keys.json'.format(node_dir.rstrip('/config'), 'user' + str(i))], shell=True)
        subprocess.call(['gaiad --home {0} --keyring-backend=test add-genesis-account $(gaiad --home {0} --keyring-backend=test keys show {1} -a) 1000000000000stake,10000000000coins'.format(node_dir.rstrip('/config'), 'user' + str(i))], shell=True)

new_genesis = node_dir + 'genesis.json'

# UNCOMMENT THIS TO MAKE BLOCK CREATION NEAR INSTANT. NEEDS TO BE ONLY 1ms AFTER THE PREVIOUS BLOCK HAS BEEN CREATED
#with fileinput.FileInput(new_genesis, inplace=True) as file:
#    for line in file:
#        print(line.replace('"time_iota_ms": "1000"', '"time_iota_ms": "1"'), end='')

# Replace every node's genesis with the new genesis containing the newly added account
for node_dir in node_directories[1:]:
    shutil.copy2(new_genesis, node_dir + 'genesis.json')
 
# Replace values in the app.toml and config.toml to allow the nodes to connect to the testnet
for node_dir in node_directories:
    current_configuration_template = make_replacements(main_configuration_template, port_sequence)
    target_configs.append(current_configuration_template)
    current_app_template = make_replacements(app_template, port_sequence)
    target_apps.append(current_app_template)
    port_sequence += port_increment

    # Make sure node directory exists
    os.makedirs(os.path.dirname(node_dir), exist_ok=True)

    # Save the changed config.toml data 
    with open(node_dir + 'config.toml', 'w') as f:
        f.write(current_configuration_template)

    # Save the changed app.toml data 
    with open(node_dir + 'app.toml', 'w') as f:
        f.write(current_app_template)

    
    proc = subprocess.Popen(['gaiad', 'start', '--home', node_dir.rstrip('/config'), '--x-crisis-skip-assert-invariants'], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

#time.sleep(300)


