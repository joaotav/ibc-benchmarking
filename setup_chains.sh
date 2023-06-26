#!/bin/bash

display_usage() {
  echo -e "$1"
  echo " Usage: ./$(basename $BASH_SOURCE)  -n <NUMBER_OF_NODES> -a <FUNDED_ACCOUNTS> -t [TIMEOUT_COMMIT]"
  echo -e "\n Options: \n"
  echo "   --nodes          | -n       Number of consensus nodes to run for each chain."
  echo "   --accounts       | -a       Number of funded accounts initialized in the source chain's genesis."
  echo "   --timeout-commit | -t       Minimum block interval in seconds (default: 5 seconds)."
  echo -e "\n Example: ./$(basename $BASH_SOURCE) -n 5 -a 10 -t 5 \n"
  exit 1
}



while [[ $# -gt 0 ]]; do
  case $1 in
    -n|--nodes)
      NUM_NODES="$2"
      shift # shift argument
      shift # shift value
      ;;
    -a|--accounts)
      NUM_ACCOUNTS="$2"
      shift 
      shift 
      ;;
    -t|--timeout-commit)
      TIMEOUT_COMMIT="$2"
      shift
      shift
      ;;
    -h|--help)
      display_usage
      ;;
    -*|--*)
      echo " Unknown option $1"
      display_usage
      ;;
     *)
      display_usage
      ;;
  esac
done


if [[ -z "$NUM_NODES" || -z "$NUM_ACCOUNTS" ]]; then
  display_usage " Missing required parameter. Please check if all parameters were specified.\n"
  exit 1
fi


# Stop running hermes processes
killall hermes &> /dev/null 2>&1

# Stop running gaiad processes
killall gaiad &> /dev/null 2>&1

sleep 1

echo "[+] Generating testnet nodes..."
# Start two gaiad chains with multiple nodes and configure them
python3 setup_testnet.py blockchain0 defaults_chain0.txt $NUM_NODES $NUM_ACCOUNTS 'true' $TIMEOUT_COMMIT # chain0
python3 setup_testnet.py blockchain1 defaults_chain1.txt $NUM_NODES $NUM_ACCOUNTS 'false' $TIMEOUT_COMMIT # chain1

sleep 1


# Add user keys to hermes
echo "[+] Adding funded accounts' keys to relayer keyring..."

# Add a key and omit the name. This will use the default value for name, 
# testkey, (defined in the config.toml file). This key will be used by the relayer to create the channel.
hermes --config hermes_config.toml keys add --chain blockchain0 --overwrite --key-file $(pwd)/blockchain0/node0/gaiad/testkey_hermes0_chain0_keys.json
hermes --config hermes_config.toml keys add --chain blockchain1 --overwrite --key-file $(pwd)/blockchain1/node0/gaiad/testkey_hermes0_chain1_keys.json 
#hermes -c hermes_config.toml keys add blockchain2 -f $(pwd)/chain2/node0/gaiad/testkey_keys.json


# Kill gaiad daemons that were started when creating the testnet
killall gaiad &> /dev/null 2>&1

sleep 1


for (( i=1; i<=$NUM_ACCOUNTS; i++ ));
do
    hermes --config hermes_config.toml keys add --chain blockchain0 --overwrite --key-file $(pwd)/blockchain0/node0/gaiad/user"$i"_keys.json --key-name user"$i"
#    hermes -c hermes_config.toml keys add chain1 -f $(pwd)/chain1/node0/gaiad/user"$i"_keys.json --name user"$i"
done 


echo "[+] Setting up remote machines..."

#  Copy testnet and node data to other machines
machine_addresses=("" "" "" "" "") # Machines running tendermint nodes

# For all the machines in the list, except the first one (this one), sync blockchain data
for machine in "${machine_addresses[@]:1}"
do
    ssh jotavio@"${machine}" killall gaiad &> /dev/null 2>&1
    ssh jotavio@"${machine}" rm -r /home/mula/jotavio/ibc_benchmark/blockchain0 &> /dev/null 2>&1
    ssh jotavio@"${machine}" rm -r /home/mula/jotavio/ibc_benchmark/blockchain1 &> /dev/null 2>&1
    rsync -a ~/ibc_benchmark/blockchain0 jotavio@${machine}:/home/mula/jotavio/ibc_benchmark/
    rsync -a ~/ibc_benchmark/blockchain1 jotavio@${machine}:/home/mula/jotavio/ibc_benchmark/
done


# Start the blockchain nodes in every machine
for node_num in `seq 0 1 $(( $NUM_NODES - 1 ))`
do
    machine_index=$(( $node_num % 5 ))
    ssh jotavio@"${machine_addresses[$machine_index]}" "killall hermes &> /dev/null 2>&1" # Kill running hermes processes in all machines
    ssh jotavio@"${machine_addresses[$machine_index]}" "nohup /home/mula/jotavio/go/bin/gaiad start --home /home/mula/jotavio/ibc_benchmark/blockchain0/node${node_num}/gaiad --x-crisis-skip-assert-invariants --log_level error > /dev/null 2>&1 &"
    ssh jotavio@"${machine_addresses[$machine_index]}" "nohup /home/mula/jotavio/go/bin/gaiad start --home /home/mula/jotavio/ibc_benchmark/blockchain1/node${node_num}/gaiad --x-crisis-skip-assert-invariants --log_level error > /dev/null 2>&1 &"
done


ssh ... "/home/mula/jotavio/.cargo/bin/hermes --config /home/mula/jotavio/ibc_benchmark/hermes_config.toml keys add --chain blockchain0 --overwrite --key-file /home/mula/jotavio/ibc_benchmark/blockchain0/node0/gaiad/testkey_hermes1_chain0_keys.json"

ssh ... "/home/mula/jotavio/.cargo/bin/hermes --config /home/mula/jotavio/ibc_benchmark/hermes_config.toml keys add --chain blockchain1 --overwrite --key-file /home/mula/jotavio/ibc_benchmark/blockchain1/node0/gaiad/testkey_hermes1_chain1_keys.json"

echo "[+] Waiting for nodes to synchronize before establishing cross-chain channel..."

# Let the blockchain nodes synchronize before establishing cross-chain channel
sleep 45

echo "[+] Creating channel to relay packets between chain0 and chain1..."
# Create a path to relay packets between chain0 and chain1

hermes --config hermes_config.toml create client --host-chain blockchain0 --reference-chain blockchain1
hermes --config hermes_config.toml create client --host-chain blockchain1 --reference-chain blockchain0

hermes --config hermes_config.toml create connection --a-chain blockchain0 --b-chain blockchain1

hermes --config hermes_config.toml create connection --a-chain blockchain0 --a-client 07-tendermint-0 --b-client 07-tendermint-0

hermes --config hermes_config.toml create channel --a-chain blockchain0 --a-connection connection-0 --a-port transfer --b-port transfer --order unordered

# hermes --config hermes_config.toml create channel --a-chain blockchain0 --b-chain blockchain1 --a-port transfer --b-port transfer --new-client-connection


