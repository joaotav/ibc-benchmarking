import sys
import json
import datetime 
import dateutil.parser
import codecs
import subprocess

def usage():
    print("[+] Usage: ./{} <path_to_data_directory> <source_chain_id> <destination_chain_id> <n_users> <n_txs> <messages_per_tx>".format(sys.argv[0].lstrip("/.")))


def read_file(data_dir, filename):
    # Read data from file line by line
    with open(data_dir + filename, "r") as f:
        raw_data = f.readlines()
        
    return raw_data

def get_n_validators(node_addr):
    result = subprocess.check_output(["curl -X GET -s '{}/validators' | jq '.result.total' ".format(node_addr)], shell=True)
    n_validators = int(result.decode("utf-8").strip('"\n'))
    return n_validators


def calc_average_block_time(block_data):
    block_times = []
    for i in range(len(block_data) - 1):
        current_block = dateutil.parser.parse(block_data[i]["block_time"])
        next_block = dateutil.parser.parse(block_data[i+1]["block_time"])
        time_diff = (next_block - current_block).total_seconds()
        block_times.append(time_diff)
        
    avg_block_time = sum(block_times) / len(block_times)
    return avg_block_time


def get_benchmark_length(block_data):
    first_block_time = dateutil.parser.parse(block_data[0]["block_time"])
    last_block_time = dateutil.parser.parse(block_data[-1]["block_time"])
    benchmark_length = (last_block_time - first_block_time).total_seconds()
    return benchmark_length


def count_messages(block_data):
    transfer_msgs = 0 # Packet transfer messages
    recv_msgs = 0 # Messages to signal transfers were received
    ack_msgs = 0 # Messages to acknowledge that transfers were received
    timeout_msgs = 0 # Messages to inform that a tx timeout has occured

    for block in block_data:
        for tx in block["transactions"]:
            transfer_msgs += tx["MsgTransfer"]
            recv_msgs += tx["MsgRecvPacket"]
            ack_msgs += tx["MsgAcknowledgement"]
            timeout_msgs += tx["MsgTimeout"]

    return transfer_msgs, recv_msgs, ack_msgs, timeout_msgs


def write_results(data_dir, results, filename):
    # Write benchmarking results to a file
    with open(data_dir + filename, "w") as f:
        for metric in results:
            for line in metric:
                f.write(str(line) + '\n')
            f.write("\n" + 70 * '-' + '\n')


def display_results(results):
    # Display the benchmark results
    for metric in results:
        for line in metric:
            print(line)
        print("\n" + 70 * '-') # Separator between metrics

    return


def get_size_in_bytes(encoded_tx_data):   
    decoded_data = codecs.decode(bytes(encoded_tx_data, "utf-8"), "base64")
    size = len(decoded_data)
    return size


def get_detailed_tx_size(block_data):
    transfer_info = [] # Store transfer transactions and their size in bytes
    recv_info = [] # Store recv transactions and their size in bytes
    ack_info = [] # Store ack transactions and their size in bytes
    timeout_info = []
    block_info = []
    # Now we need to estimate the size of data in block without any transactions in it
    # From empirical observation: blocks with 1 validator ~ 0.5kb; 5 val = 1kb; 10 val ~ 1.5kb; 15 val ~ 2kb; 20 val ~ 2.5kb
    # Should be good enough to estimate block header size
   
    
    for block in block_data: # For each block in the JSON data
        block_info.append(block["block_size"]) # Block size in bytes, retrieved from Tendermint RPC
        
        for tx in block["transactions"]: # For each transaction inside the block 
            # Count how many of each IBC message the transaction contains
            msg_count = {"transfer": tx["MsgTransfer"], "recv": tx["MsgRecvPacket"], "ack": tx["MsgAcknowledgement"], "timeout": tx["MsgTimeout"]}
            
            # Transactions always contain one or more of only one type of message. 
            # Check which type of message has the most occurrences, i,e, the one that is not 0,
            # get its size and append to the corresponding message type list
            if max(msg_count, key = msg_count.get) == "transfer" and msg_count["transfer"] > 0:
                transfer_info.append([msg_count["transfer"], get_size_in_bytes(tx["tx_data"])])

            elif max(msg_count, key = msg_count.get) == "recv" and msg_count["recv"] > 0:
                recv_info.append([msg_count["recv"], get_size_in_bytes(tx["tx_data"])])

            elif max(msg_count, key = msg_count.get) == "ack" and msg_count["ack"] > 0:
                ack_info.append([msg_count["ack"], get_size_in_bytes(tx["tx_data"])])

            elif max(msg_count, key = msg_count.get) == "timeout" and msg_count["timeout"] > 0:
                timeout_info.append([msg_count["timeout"], get_size_in_bytes(tx["tx_data"])])

    
    return transfer_info, recv_info, ack_info, timeout_info, block_info


def get_tx_size(block_data):
    transfer_info = []
    recv_info = []
    ack_info = []
    timeout_info = []
    block_info = []

    for block in block_data:
        block_info.append(block["block_size"])
        
        for tx in block["transactions"]:
            msg_count = {"transfer": tx["MsgTransfer"], "recv": tx["MsgRecvPacket"], "ack": tx["MsgAcknowledgement"],"timeout": tx["MsgTimeout"] }

            if max(msg_count, key = msg_count.get) == "transfer" and msg_count["transfer"] > 0:
                transfer_info.append(msg_count["transfer"])

            elif max(msg_count, key = msg_count.get) == "recv" and msg_count["recv"] > 0:
                recv_info.append(msg_count["recv"])

            elif max(msg_count, key = msg_count.get) == "ack" and msg_count["ack"] > 0:
                ack_info.append(msg_count["ack"])

            elif max(msg_count, key = msg_count.get) == "timeout" and msg_count["timeout"] > 0:
                timeout_info.append(msg_count["timeout"])

    return transfer_info, recv_info, ack_info, timeout_info, block_info        


def calc_data_size(transfer_info, recv_info, ack_info, timeout_info, block_info, chain_id, last_throughput_block):
    results = list()
    
    num_transfer_txs = len(transfer_info)
    num_recv_txs = len(recv_info)
    num_ack_txs = len(ack_info)
    num_timeout_txs = len(timeout_info)
    num_total_txs = num_transfer_txs + num_recv_txs + num_ack_txs + num_timeout_txs


    num_transfer_msgs = sum(transfer_info)
    num_recv_msgs = sum(recv_info)
    num_ack_msgs = sum(ack_info)
    num_timeout_msgs = sum(timeout_info)
    num_total_messages = num_transfer_msgs + num_recv_msgs + num_ack_msgs + num_timeout_msgs

    total_block_data = sum(block_info[:last_throughput_block]) # All data committed to the blockchain including txs, messages and block information

    if num_transfer_txs > 0:
        avg_transfers_per_tx = num_transfer_msgs / num_transfer_txs

    if num_recv_txs > 0:    
        avg_recvs_per_tx = num_recv_msgs / num_recv_txs

    if num_ack_txs > 0:       
        avg_acks_per_tx = num_ack_msgs / num_ack_txs

    results.append("[+] {} analysis for chain '{}':\n".format("Data", chain_id))
    #results.append(" Number of blocks finalized: {}".format(len(block_info)) )
    results.append(" Collective size of all blocks (excl. empty blocks at the end): {}".format(format_size_unit(total_block_data)))
    results.append(" Avg. block size (excl. empty blocks at the end): {}".format(format_size_unit(total_block_data / len(block_info[:last_throughput_block]))))
    results.append(" Number of transactions committed to the blockchain: {}".format(num_total_txs))
    results.append(" Number of messages committed in the blockchain: {}".format(num_total_messages))
    results.append("")
    
    results.append(" Number of transactions containing transfer messages on {}: {}".format(chain_id, num_transfer_txs))
    #if num_transfer_txs > 0: # If there are transfer messages, display info about them
    results.append(" Number of transfer messages on {}: {}".format(chain_id, num_transfer_msgs))
    #results.append(" Avg. number of transfer messages per tx: {:.2f}".format(avg_transfers_per_tx))
    results.append("")

    results.append(" Number of transactions containing recv messages on {}: {}".format(chain_id, num_recv_txs))
    #if num_recv_txs > 0: # If there are recv messages, display info about them
    results.append(" Number of recv messages on {}: {}".format(chain_id, num_recv_msgs))
    #results.append(" Avg. number of recv messages per tx: {:.2f}".format(avg_recvs_per_tx))
    results.append("")

    results.append(" Number of transactions containing ack messages on {}: {}".format(chain_id, num_ack_txs))
    #if num_ack_txs > 0: # If there are ack messages, display info about them
    results.append(" Number of ack messages on {}: {}".format(chain_id, num_ack_msgs))
    #results.append(" Avg. number of ack messages per tx: {:.2f}".format(avg_acks_per_tx))
    results.append("")
    
    results.append(" Number of transactions containing timeout messages on {}: {}".format(chain_id, num_timeout_txs))
    results.append(" Number of timeout messages on {}: {}".format(chain_id, num_timeout_msgs))
    #results.append(" Avg. number of recv messages per tx:")
    return results

def calc_detailed_data_size(transfer_info, recv_info, ack_info, timeout_info, block_info, chain_id):
    results = list()

    num_transfer_txs = len(transfer_info)
    num_recv_txs = len(recv_info)
    num_ack_txs = len(ack_info)
    num_timeout_txs = len(timeout_info)
    num_total_txs = num_transfer_txs + num_recv_txs + num_ack_txs + num_timeout_txs

    num_transfer_msgs = sum([x[0] for x in transfer_info])
    num_recv_msgs = sum([x[0] for x in recv_info])
    num_ack_msgs = sum([x[0] for x in ack_info])
    num_timeout_msgs = sum([x[0] for x in timeout_info])
    num_total_messages = num_transfer_msgs + num_recv_msgs + num_ack_msgs + num_timeout_msgs

    all_transfer_data = sum([x[1] for x in transfer_info]) # Sum the size of all transfer transactions
    all_recv_data = sum([x[1] for x in recv_info]) # Sum the size of all recv transactions
    all_ack_data = sum([x[1] for x in ack_info]) # Sum the size of all ack transactions
    all_timeout_data = sum([x[1] for x in timeout_info])

    total_tx_data = all_transfer_data + all_recv_data + all_ack_data + all_timeout_data # All tx data committed to the blockchain for the IBC transfers
    total_block_data = sum(block_info) # All data committed to the blockchain including txs, messages and block information

    # Initialize variables as 0 and only add to results if they changed to != 0
    avg_transfer_tx_size = 0
    avg_data_per_transfer_msg = 0
    avg_recv_tx_size = 0
    avg_data_per_recv_msg = 0
    avg_ack_tx_size = 0
    avg_data_per_ack_msg = 0

    if num_transfer_txs > 0:
        avg_transfer_tx_size = all_transfer_data / num_transfer_txs # Average size in bytes of each tx with transfer messages
        avg_data_per_transfer_msg = all_transfer_data / num_transfer_msgs
        avg_transfers_per_tx = num_transfer_msgs / num_transfer_txs

    if num_recv_txs > 0:    
        avg_recv_tx_size = all_recv_data / num_recv_txs # Average size in bytes of each tx with recv messages
        avg_data_per_recv_msg = all_recv_data / num_recv_msgs
        avg_recvs_per_tx = num_recv_msgs / num_recv_txs

    if num_ack_txs > 0:       
        avg_ack_tx_size = all_ack_data / num_ack_txs # Average size in bytes of each tx with ack messages
        avg_data_per_ack_msg = all_ack_data / num_ack_msgs
        avg_acks_per_tx = num_ack_msgs / num_ack_txs

    
    results.append("[+] {} analysis for chain '{}':\n".format("Data", chain_id))
    results.append(" Number of blocks finalized: {}".format(len(block_info)) )
    results.append(" Collective size of all blocks: {}".format(format_size_unit(total_block_data)))
    results.append(" Avg. block size: {}".format(format_size_unit(total_block_data / len(block_info))))
    results.append(" Number of transactions committed to the blockchain: {}".format(num_total_txs))
    results.append(" Number of messages inside transactions: {}".format(num_total_messages))
    results.append(" Collective size of all transactions: {}".format(format_size_unit(total_tx_data)))
    results.append("")
    
    results.append(" Number of transactions containing transfer messages: {}".format(num_transfer_txs))
    if num_transfer_txs > 0: # If there are transfer messages, display info about them
        results.append(" Collective size of transfer transactions: {}".format(format_size_unit(all_transfer_data)))
        results.append(" Avg. size of each transfer tx: {}".format(format_size_unit(avg_transfer_tx_size)))
        results.append(" Number of transfer messages: {}".format(num_transfer_msgs))
        results.append(" Avg. size of each transfer message: {}".format(format_size_unit(avg_data_per_transfer_msg)))
        results.append(" Avg. number of transfer messages per tx: {:.2f}".format(avg_transfers_per_tx))
    results.append("")

    results.append(" Number of transactions containing recv messages: {}".format(num_recv_txs))
    if num_recv_txs > 0: # If there are recv messages, display info about them
        results.append(" Collective size of recv transactions {}".format(format_size_unit(all_recv_data)))
        results.append(" Avg. size of each recv tx: {}".format(format_size_unit(avg_recv_tx_size)))
        results.append(" Number of recv messages: {}".format(num_recv_msgs))
        results.append(" Avg. size of each recv message: {}".format(format_size_unit(avg_data_per_recv_msg)))
        results.append(" Avg. number of recv messages per tx: {:.2f}".format(avg_recvs_per_tx))
    results.append("")

    results.append(" Number of transactions containing ack messages: {}".format(num_ack_txs))
    if num_ack_txs > 0: # If there are ack messages, display info about them
        results.append(" Collective size of ack transactions: {}".format(format_size_unit(all_ack_data)))
        results.append(" Avg. size of each ack tx: {}".format(format_size_unit(avg_ack_tx_size)))
        results.append(" Number of ack messages: {}".format(num_ack_msgs))
        results.append(" Avg. size of each ack message: {}".format(format_size_unit(avg_data_per_ack_msg)))
        results.append(" Avg. number of ack messages per tx: {:.2f}".format(avg_acks_per_tx))

    return results
    

def get_transfer_status(src_transfers, dst_recvs, src_acks, src_timeouts, n_ibc_transfers):
    timed_out = src_timeouts # Number of timed out messages

    if src_acks > src_transfers: # If there are more acks than we transferred, happens for unknown reasons even after clearing previous packets. 
        finished = src_transfers # All the transfers were finished 
    else:
        finished = src_acks # Transfers that were acknowledged were completed

    if dst_recvs > src_transfers:
        partially_finished = src_transfers
    else:
        partially_finished = dst_recvs - src_acks

    if partially_finished > (src_transfers - src_acks - timed_out): # Recvs were sent from the destination but the source timed out before the ack was received
        partially_finished = src_transfers - src_acks - timed_out # Remove those recvs from the partially finished, since the transfers timed out in the source

    initiated = src_transfers - (partially_finished + finished + timed_out)
    not_initiated = n_ibc_transfers - src_transfers

    return finished, partially_finished, initiated, not_initiated, timed_out


def calc_success_rate(src_data, dst_data, n_users, n_txs, msgs_per_tx, src_chain_id, dst_chain_id):
    n_ibc_transfers = n_users * (n_txs * msgs_per_tx) 
    src_transfers, src_recvs, src_acks, src_timeouts = count_messages(src_data)
    dst_transfers, dst_recvs, dst_acks, dst_timeouts = count_messages(dst_data)
    finished, partially_finished, initiated, not_initiated, timed_out = get_transfer_status(src_transfers, dst_recvs, src_acks, src_timeouts, n_ibc_transfers)
    finished_percentage = finished * 100 / n_ibc_transfers
    partially_finished_percentage = partially_finished * 100 / n_ibc_transfers
    timed_out_percentage = timed_out * 100 / n_ibc_transfers
    initiated_percentage = initiated * 100 / n_ibc_transfers
    not_initiated_percentage = not_initiated * 100 / n_ibc_transfers
    
    results = list()

    results.append("[+] Success rate analysis for channel '{} -> {}':\n".format(src_chain_id, dst_chain_id))

    results.append(" IBC transfers submitted to '{}': {}".format(src_chain_id, n_ibc_transfers))
    results.append(" 'Transfer' messages committed to '{}': {}".format(src_chain_id, src_transfers))
    results.append(" 'Receive' messages committed to '{}': {}".format(dst_chain_id, dst_recvs))
    results.append(" 'Acknowledgement' messages committed to '{}': {}".format(src_chain_id, src_acks))
    results.append(" 'Timeout' messages committed' to '{}' (source chain): {}".format(src_chain_id, src_timeouts))
    #results.append(" 'Timeout' messages committed'' to '{}': {}".format(dst_chain_id, dst_timeouts))

    results.append("")
    results.append(" Transfers completed (transfer, recv, ack): {} ({:.2f}%)".format(finished, finished_percentage))
    results.append(" Transfers partially completed (transfer, recv): {} ({:.2f}%)".format(partially_finished, partially_finished_percentage))
    results.append(" Transfers only initiated (transfer): {} ({:.2f}%)".format(initiated, initiated_percentage))
    results.append(" Transfers not initiated (submitted but not committed): {} ({:.2f}%)".format(not_initiated, not_initiated_percentage))
    results.append(" Timed out transfers: {} ({:.2f}%)".format(timed_out, timed_out_percentage))

    return results


def calc_throughput(block_data, last_throughput_block):
    chain_id = block_data[0]["chain-id"]
    block_data = block_data[:last_throughput_block]
    n_blocks = len(block_data)
    n_empty_blocks = sum([1 for block in block_data if len(block["transactions"]) == 0])
    percentage_empty_blocks = n_empty_blocks *  100 / n_blocks
    n_transactions = sum([len(block["transactions"]) for block in block_data])
    avg_txs_per_block = n_transactions / n_blocks

    #avg_txs_per_block_non_empty = n_transactions / (n_blocks - n_empty_blocks)
    transfer_msgs, recv_msgs, ack_msgs, timeout_msgs = count_messages(block_data) 
    n_messages = transfer_msgs + recv_msgs + ack_msgs + timeout_msgs
    
    if n_transactions == 0:
        avg_msgs_per_tx = 0
    else:
        avg_msgs_per_tx = n_messages / n_transactions

    avg_msgs_per_block = avg_msgs_per_tx * avg_txs_per_block
    #avg_msgs_per_block_non_empty = avg_msgs_per_tx * avg_txs_per_block_non_empty
    avg_block_time = calc_average_block_time(block_data)
    benchmark_seconds = get_benchmark_length(block_data)
    txs_per_sec = n_transactions / benchmark_seconds
    messages_per_sec = n_messages / benchmark_seconds
    transfers_per_sec = transfer_msgs / benchmark_seconds
    
    results = list()
    
    results.append("[+] {} analysis for chain '{}':\n".format("Throughput", chain_id))
    results.append(" Blocks finalized: {}".format(n_blocks))
    results.append("")
    results.append(" Avg. block time: {:.3f} seconds".format(avg_block_time))
    results.append(" Number of empty blocks: {} ({:.2f}%)".format(n_empty_blocks, percentage_empty_blocks))
    results.append("")
    results.append(" Avg. number of txs per block (counting empty blocks): {:.2f}".format(avg_txs_per_block))
    #results.append(" Avg. number of txs per block (excluding empty blocks): {:.2f}".format(avg_txs_per_block_non_empty))
    results.append(" Avg. number of txs per second(transfer, recv, ack): {:.2f}".format(txs_per_sec))
    results.append("")
    results.append(" Avg. number of messages per tx: {:.2f}".format(avg_msgs_per_tx))
    results.append(" Avg. number of messages per block (counting empty blocks): {:.2f}".format(avg_msgs_per_block))
    #results.append(" Avg. number of messages per block (excluding empty blocks): {:.2f}".format(avg_msgs_per_block_non_empty))
    results.append(" Avg. number of messages per second (transfer, recv, ack, timeout): {:.2f}".format(messages_per_sec))
    results.append(" Avg. number of transfers per second: {:.2f}".format(transfers_per_sec))
    results.append("")

    return results


def parse_transfer_latency(data):
    transfer_txs = list()
    waiting = []
    confirmed = []
    
    for i in range(len(data)):
        if "wait_for_block_commits: waiting for commit of tx hashes" in data[i]:
            waiting.append(data[i])
        elif "wait_for_block_commits: retrieved" in data[i]:
            confirmed.append(data[i])
    
    # Match transfers waiting for confirmation with transfer confirmation messages
    for i in range(len(waiting)):
        tx_hashes = waiting[i].split("tx hashes(s)")[-1].split("id")[0].replace(" ", "").split(",")
        if i > (len(confirmed) - 1): 
            break # No more confirmation messages in the logs, cannot match the confirmation times for the remaining sent transfers, break
        else:        
            delay = confirmed[i].split("after")[-1].split()[0]
            if delay[-2:] == "ms":
                delay = delay.rstrip("ms")
                delay = float(delay) / 1000

            for tx_hash in tx_hashes:
                transfer_txs.append([tx_hash.strip(), delay])

    return transfer_txs


def parse_ack_latency(data):
    # Parse acknowledgement transaction data into a list of [tx_hash, confirmation_latency] pairs 
    # Currently the same as parse_recv_latency but kept in a separate function for modularity
    ack_txs = list()

    for i in range(len(data)):
        if "transactions confirmed" in data[i]:
            _ = data[i].split(";")
            tx_hashes = _[1:] # Second half of string, containing confirmed tx hashes
            info = _[0] # First half of the string, containing thread, packet and time information
            info = info.split(":")
            delay = info[-2].split()[-2].split("=")
            delay = delay[-1]
            if delay.endswith("ms"):
                # Strip the 'ms' for milliseconds, transform into seconds and change to float to perform operations
                delay = delay.rstrip("ms")
                delay = float(delay) / 1000
            else:
                # Strip the 's' for seconds and change to float to perform operations
                delay = float(delay.rstrip("s")) 

            for tx_hash in tx_hashes:    
                ack_txs.append([tx_hash.strip(), delay])
    return ack_txs


def parse_recv_latency(data):
    # Parse recv transaction data into a list of [tx_hash, confirmation_latency] pairs 
    # Currently the same as parse_ack_latency but kept in a separate function for modularity
    recv_txs = list()

    for i in range(len(data)):
        if "transactions confirmed" in data[i]:
            _ = data[i].split(";")
            tx_hashes = _[1:]
            info = _[0]
            info = info.split(":")
            delay = info[-2].split()[-2].split("=")
            delay = delay[-1]
            if delay.endswith("ms"):
                # Strip the 'ms' for milliseconds, transform into seconds and change to float to perform operations
                delay = delay.rstrip("ms")
                delay = float(delay) / 1000
            else:
                # Strip the 's' for seconds and change to float to perform operations
                delay = float(delay.rstrip("s"))

            for tx_hash in tx_hashes:    
                recv_txs.append([tx_hash.strip(), delay])
    return recv_txs


def calc_tx_distribution(block_data, chain_id):
    # Get the distribution of transactions in the blocks generated during benchmark
    tx_distribution = {}
    results = list()
    for block in block_data: # For each block
        num_txs = block['num_transactions'] # Retrieve number of txs inside block
        if num_txs in tx_distribution.keys():
            tx_distribution[num_txs] += 1  # Add occurrence to dictionary (1 more block with 'num_txs' transactions)
        else:
            tx_distribution[num_txs] = 1 # Initialize key on dictionary (blocks containing 'num_txs' transactions)


    results.append("[+] Transaction distribution analysis for {}:\n".format(chain_id))
    for key in sorted(tx_distribution.keys()):
        results.append(" {} tx(s): {} block(s)".format(key, tx_distribution[key]))
    
    return results


def format_size_unit(size):
    if size >= 1024000:
        size = "{:.2f} MB".format((size / 1024 / 1024)) # Include 2 decimal places if over 1 MB
    elif size >= 1024:
        size = "{:.2f} kB".format((size / 1024)) # Include 2 decimal places if over 1 kB
    else:
        size = "{:.0f} bytes".format(size) # Show no decimal places if represented in bytes
    return size


def format_time_unit(time):
    # Change time representation to milliseconds if < 1 second or seconds if > 1 second
    if time == "N/A":
        return time

    elif time < 1:
        # If less than 1 second, use milliseconds representation
        time = "{:.0f}".format(time * 1000)
        time = time + "ms"
    else:
        # If equal or greater than 1, use seconds representation
        time = "{:.3f}".format(time)
        time = time + "s"

    return time

def parse_txs_from_blocks(data):
    transactions = {}
    for block in data:
        for tx in block['transactions']:
            tx_hash = tx['tx_hash']
            num_transfer_msgs = tx['MsgTransfer']
            num_recv_msgs = tx['MsgRecvPacket']
            num_ack_msgs = tx['MsgAcknowledgement']
            num_timeout_msgs = tx['MsgTimeout']
            transactions[tx_hash] = {'MsgTransfer': num_transfer_msgs, 'MsgRecvPacket': num_recv_msgs, 'MsgAcknowledgement': num_ack_msgs, 'MsgTimeout': num_timeout_msgs} 
            
    return transactions


def calc_round_trip_time(relayer_data, src_chain_id, dst_chain_id, src_txs, dst_txs, data_dir):
    transfer_broadcasts = []
    recv_broadcasts = []
    ack_broadcasts = []
    ack_confirmations = []    
    ack_hashes = []
    rt_times = []    
    transfer_times = []
    recv_times = []
    ack_times = []
    ack_confirmation_times = []
    transfer_hashes = []
    results = []

    for event in relayer_data:
        if "send_tx_with_account_sequence_retry{id=" + dst_chain_id + "}: broadcast_tx_sync" in event and "ERROR" not in event: # Destination chain broadcasts txs containing recv packets
            timestamp = event[:27]
            tx_hash = event.split("transaction::Hash")[-1].split()[0].strip("()") # Get transaction hash of broadcasted transaction
            recv_broadcasts.append([timestamp, tx_hash])
        elif "send_tx_with_account_sequence_retry{id=" + src_chain_id + "}: broadcast_tx_sync" in event and "ERROR" not in event: # Source chain broadcasts txs containing ack packets
            timestamp = event[:27]
            tx_hash = event.split("transaction::Hash")[-1].split()[0].strip("()") # Get transaction hash of broadcasted transaction
            ack_broadcasts.append([timestamp, tx_hash])
            ack_hashes.append(tx_hash) # Ack tx hash, used later to check if a confirmed tx hash is an ack or a recv tx
        elif 'event="SendPacket"' in event and "ERROR" not in event:
            timestamp = event[:27]
            tx_hash = event.split(" ")[-2]
            if tx_hash not in transfer_hashes: # Every transaction has many SendPacket events, one for each message, if the transaction hash has already been tracked, skip
                transfer_broadcasts.append([timestamp, tx_hash])
                transfer_hashes.append(tx_hash)

    for event in relayer_data:
        if "transactions confirmed" in event: # If a transaction has been confirmed
            # Check how many transaction hashes have been confirmed
            tx_hashes = event.split(";")[1:] # Get the hashes of the confirmed transactions (may be one or more)
            for tx_hash in tx_hashes:                  
                tx_hash = tx_hash.strip() # Remove whitespace surrounding transaction hash
                # Compare to transaction hashes of acknowledgement transactions that have been broadcasted
                if tx_hash in ack_hashes: # If it is a transaction containing acknowledgement messages
                    timestamp = event[:27]
                    ack_confirmations.append([timestamp, tx_hash])


    for transfer in transfer_broadcasts:
        transfer_tx_hash = transfer[1]
        transfer_timestamp = transfer[0]
        num_transfers = src_txs[transfer_tx_hash]['MsgTransfer']
        for i in range(num_transfers):
            transfer_times.append(transfer_timestamp)
        

    for recv in recv_broadcasts:
        recv_tx_hash = recv[1]
        recv_timestamp = recv[0]
        if recv_tx_hash in dst_txs.keys():
            num_recvs = dst_txs[recv_tx_hash]['MsgRecvPacket']
            for i in range(num_recvs):
                recv_times.append(recv_timestamp)
        else:        
            print("######## UNKNOWN RECV TX HASH #########")
            print(recv_tx_hash)
 

    for confirmation in ack_confirmations:
        confirmation_hash = confirmation[1]
        confirmation_timestamp = confirmation[0]
        # Confirmation hash is the same as ack hash, it merely confirms the commitment of the tx with this specific hash that was broadcasted before
        num_confirmations = src_txs[confirmation_hash]['MsgAcknowledgement']
        for i in range(num_confirmations):
            ack_confirmation_times.append(confirmation_timestamp)


    for ack in ack_broadcasts:
        ack_tx_hash = ack[1]
        ack_timestamp = ack[0]
        if ack_tx_hash in [x[1] for x in ack_confirmations]: # Only count ack tx if its hash is in the confirmed acks list, i.e, not timed out
            num_acks = src_txs[ack_tx_hash]['MsgAcknowledgement']
            for i in range(num_acks):
                ack_times.append(ack_timestamp)  


    completed_msg_round_trips = min(len(transfer_times), len(recv_times), len(ack_times), len(ack_confirmation_times))

    with open(data_dir + "round_trip_times.txt", "w") as f:
        header = "transfer_broadcast;recv_broadcast;ack_broadcast;ack_confirmation;round_trip_time"
        f.write(header + "\n")
        for i in range(completed_msg_round_trips):
            rtt = (dateutil.parser.parse(ack_confirmation_times[i]) - dateutil.parser.parse(transfer_times[i])).total_seconds()
            f.write("{};{};{};{};{}\n".format(transfer_times[i], recv_times[i], ack_times[i], ack_confirmation_times[i], rtt))
            rt_times.append(rtt)
        
    results.append("[+] Round trip time analysis for chains '{} -> {}':\n".format(src_chain_id, dst_chain_id))

    if len(rt_times) > 0: # If at least one message got delivered (transfer, recv, ack)
        avg_rtt = sum(rt_times)/len(rt_times)
        shortest_rtt = min(rt_times)
        longest_rtt = max(rt_times)   
        results.append(" Average round trip time: {}".format(format_time_unit(avg_rtt)))
        results.append(" Shortest round trip time: {}".format(format_time_unit(shortest_rtt)))
        results.append(" Longest round trip time: {}".format(format_time_unit(longest_rtt)))

    else: # If no messages were delivered due to congestion
        results.append(" No messages were fully delivered(transfer, recv, ack).")

    return results


def calc_latency(transfer_latency, recv_latency, ack_latency, src_chain_id, dst_chain_id):
    results = list()

    if len(transfer_latency) == 0:
        avg_transfer_latency = "N/A"
        shortest_transfer = "N/A"
        longest_transfer = "N/A"
    else:
        avg_transfer_latency = sum([tx[1] for tx in transfer_latency]) / len(transfer_latency)
        shortest_transfer = min(transfer_latency, key = lambda transfer_latency:transfer_latency[1])[1]
        longest_transfer = max(transfer_latency, key = lambda transfer_latency:transfer_latency[1])[1]

    if len(recv_latency) == 0:
        avg_recv_latency = "N/A"
        shortest_recv = "N/A"
        longest_recv = "N/A"
    else:
        avg_recv_latency = sum([tx[1] for tx in recv_latency]) / len(recv_latency)
        shortest_recv = min(recv_latency, key = lambda recv_latency:recv_latency[1])[1]
        longest_recv = max(recv_latency, key = lambda recv_latency:recv_latency[1])[1]

    if len(ack_latency) == 0:
        avg_ack_latency = "N/A"
        shortest_ack = "N/A"
        longest_ack = "N/A"
    else:
        avg_ack_latency = sum([tx[1] for tx in ack_latency]) / len(ack_latency)
        shortest_ack = min(ack_latency, key = lambda ack_latency:ack_latency[1])[1]
        longest_ack = max(ack_latency, key = lambda ack_latency:ack_latency[1])[1]

    results.append("[+] {} analysis for chains '{} -> {}':\n".format("IBC messages confirmation latency", src_chain_id, dst_chain_id))

    results.append(" Avg. transfer message confirmation latency: {}".format(format_time_unit(avg_transfer_latency)))
    results.append(" Shortest transfer latency observed: {}".format(format_time_unit(shortest_transfer)))
    results.append(" Longest transfer latency observed: {}".format(format_time_unit(longest_transfer)))
    results.append("")
    results.append(" Avg. recv message confirmation latency: {}".format(format_time_unit(avg_recv_latency)))
    results.append(" Shortest recv message confirmation latency: {}".format(format_time_unit(shortest_recv)))
    results.append(" Longest recv message confirmation latency: {}".format(format_time_unit(longest_recv)))
    results.append("")
    results.append(" Avg. acknowledgement message confirmation latency: {}".format(format_time_unit(avg_ack_latency)))
    results.append(" Shortest acknowledgement message confirmation latency: {}".format(format_time_unit(shortest_ack)))
    results.append(" Longest acknowledgement message confirmation latency: {}".format(format_time_unit(longest_ack)))
    
    return results


def load_json(data):
    block_data = list()
    
    for line in data:
        block = json.loads(line)
        block_data.append(block)
    return block_data

def pretty_print_time(seconds):
    if seconds < 3600:
        elapsed = "{}m {}s".format((seconds // 60), (seconds % 60))
    else:
        elapsed = "{:02d}h {:02d}m {:02d}s".format(seconds // 3600, seconds % 3600 // 60, seconds % 3600 % 60)

    return elapsed

def get_benchmark_info(src_chain_id, dst_chain_id, n_peers, n_users, n_txs, msgs_per_tx, transfer_submission_time, waiting_time, data_collection_time):
    results = list()
    results.append("[+] Benchmark configuration summary:\n")
    results.append(" Source chain: {} ".format(src_chain_id))
    results.append(" Destination chain: {}".format(dst_chain_id))
    results.append(" Number of validators in each chain: {}".format(n_peers))
    results.append(" Number of user accounts: {}".format(n_users))
    results.append(" Transactions submitted per user: {}".format(n_txs))
    results.append(" Total number of transactions: {}".format(n_txs * n_users))
    results.append(" Transfer messages per transaction: {}".format(msgs_per_tx))
    results.append(" Total number of transfer messages: {}\n".format(msgs_per_tx * n_txs * n_users))
    results.append(" IBC transfers submission (time elapsed): {}".format(pretty_print_time(transfer_submission_time)))
    results.append(" Time waiting for empty blocks at the end of benchmark: {}".format(pretty_print_time(waiting_time)))
    results.append(" Blockchain data collection (time elapsed): {}".format(pretty_print_time(data_collection_time)))
    results.append(" Total time elapsed: {}".format(pretty_print_time(transfer_submission_time + waiting_time + data_collection_time)))

    return results

def sanitize_path(path):
    # Make sure the path can be interpreted by the read/write functions
    path = path.strip("/")
    path += "/"
    return path


def check_delay(data):
    # Helper to verify delay for transfer and ack messages
    transfer_txs = list()
    
    for i in range(len(data)):
        if "waiting for commit of tx hashes" in data[i]: 
            tx_hashes = data[i].split(")")[-1].split(",")
            delay = data[i+1].split("(")[-1] # Delay on next line 
            delay = delay.strip().strip(")")
            timestamp = data[i+1][0:19]
   
            if delay[-2:] == "ms":
                delay = delay.rstrip("ms")
                delay = float(delay) / 1000

            for tx_hash in tx_hashes:
                print(timestamp, tx_hash.strip(), delay, "TRANSFER")    


    for i in range(len(data)):
        if "confirmed after" in data[i]:
            _ = data[i].split(";")
            tx_hashes = _[1:]
            info = _[0]
            info = info.split("]")[-1].split(":")
            delay = info[0].strip()
            delay = delay[16:]
            timestamp = data[i][0:19]

            if delay[-2:] == "ms":
                # Strip the 'ms' for milliseconds, transform into seconds and change to float to perform operations
                delay = delay.rstrip("ms")
                delay = float(delay) / 1000
            else:
                # Strip the 's' for seconds and change to float to perform operations
                delay = float(delay.rstrip("s"))

            for tx_hash in tx_hashes:    
                print(timestamp, tx_hash.strip(), delay, "ACK")
    


