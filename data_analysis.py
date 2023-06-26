#!/usr/bin/env python3
from analysis_functions import *

def main():
    if len(sys.argv) != 14:
        usage()
        raise SystemExit
    
    data_dir = sanitize_path(sys.argv[1])

    src_chain_id = sys.argv[2] # String id for the source chain
    dst_chain_id = sys.argv[3] # String id for the destination chain
    src_chain_node_addr = sys.argv[4]
    n_users = int(sys.argv[5]) # Number of users submitting transactions
    n_txs = int(sys.argv[6]) # Number of transactions executed in the benchmark
    msgs_per_tx = int(sys.argv[7]) # Number of IBC messages per transaction
    tx_data_analysis = sys.argv[8] # Wheter to perform detailed tx and msg size analysis or not
    transfer_submission_time = int(sys.argv[9]) # Time for the completion of benchmarking tasks
    waiting_time = int(sys.argv[10])
    data_collection_time = int(sys.argv[11])
    src_last_throughput_block = int(sys.argv[12]) # Do not include blocks after this one for throughput calculation
    dst_last_throughput_block = int(sys.argv[13]) # Do not include blocks after this one for throughput calculation

    benchmarking_report = list()
    
    n_validators = get_n_validators(src_chain_node_addr)

    benchmarking_report.append(get_benchmark_info(src_chain_id, dst_chain_id, n_validators, n_users, n_txs, msgs_per_tx, transfer_submission_time, waiting_time, data_collection_time))

    # Read block data for source and destination chain
    src_chain_data = read_file(data_dir, "block_data_" + src_chain_id + ".txt") # Read json 
    dst_chain_data = read_file(data_dir, "block_data_" + dst_chain_id + ".txt")


    # Read transfer data from relayer log files
    # Relayer files contain log data from confirmed transactions on source and destination chains
    src_chain_latency_data = read_file(data_dir, "logs_" + src_chain_id + ".txt")
    dst_chain_latency_data = read_file(data_dir, "logs_" + dst_chain_id + ".txt")
    
    # Load data from hermes logs to calculate message round trip time
    relayer_data = read_file(data_dir, "hermes_log.txt")

    # Load json block data into dictionaries
    src_blocks = load_json(src_chain_data)
    dst_blocks = load_json(dst_chain_data)

    # Extract transaction data from block data
    src_txs = parse_txs_from_blocks(src_blocks)
    dst_txs = parse_txs_from_blocks(dst_blocks)


    # Tx distribution analysis
    benchmarking_report.append(calc_tx_distribution(src_blocks, src_chain_id))
    benchmarking_report.append(calc_tx_distribution(dst_blocks, dst_chain_id))
    

    # Throughput analysis
    benchmarking_report.append(calc_throughput(src_blocks, src_last_throughput_block))
    benchmarking_report.append(calc_throughput(dst_blocks, dst_last_throughput_block))

    # Round trip time analysis
    benchmarking_report.append(calc_round_trip_time(relayer_data, src_chain_id, dst_chain_id, src_txs, dst_txs, data_dir))
    
    # Calculate success rate given the number of blocks and confirmed transactions/messages
    benchmarking_report.append(calc_success_rate(src_blocks, dst_blocks, n_users, n_txs, msgs_per_tx, src_chain_id, dst_chain_id))
    
    # Parse relayer log data for source chain to get latency for transfer messages
    transfer_latency = parse_transfer_latency(src_chain_latency_data)
    
    # Parse relayer log data for destination chain to get latency for recv messages
    recv_latency = parse_recv_latency(dst_chain_latency_data)

    # Parse relayer log data for source chain to get latency for acknowledgement messages 
    ack_latency = parse_ack_latency(src_chain_latency_data)

    # Calculate latency
    benchmarking_report.append(calc_latency(transfer_latency, recv_latency, ack_latency, src_chain_id, dst_chain_id))


    if tx_data_analysis == "true":

        src_transfer_info, src_recv_info, src_ack_info, src_timeout_info, src_block_info = get_detailed_tx_size(src_blocks)
        dst_transfer_info, dst_recv_info, dst_ack_info, dst_timeout_info, dst_block_info = get_detailed_tx_size(dst_blocks)
    
        benchmarking_report.append(calc_detailed_data_size(src_transfer_info, src_recv_info, src_ack_info, timeout_info, src_block_info, src_chain_id))
        benchmarking_report.append(calc_detailed_data_size(dst_transfer_info, dst_recv_info, dst_ack_info, timeout_info, dst_block_info, dst_chain_id))
    
    else:
        
        src_transfer_info, src_recv_info, src_ack_info, src_timeout_info, src_block_info = get_tx_size(src_blocks)
        dst_transfer_info, dst_recv_info, dst_ack_info, dst_timeout_info, dst_block_info = get_tx_size(dst_blocks)
    
        benchmarking_report.append(calc_data_size(src_transfer_info, src_recv_info, src_ack_info, src_timeout_info, src_block_info, src_chain_id, src_last_throughput_block))
        benchmarking_report.append(calc_data_size(dst_transfer_info, dst_recv_info, dst_ack_info, dst_timeout_info, dst_block_info, dst_chain_id, dst_last_throughput_block))

    display_results(benchmarking_report)
    write_results(data_dir, benchmarking_report, "benchmarking_report.txt")

    #del src_transfer_sizes
    
    #transaction_distribution(src_blocks)
    #transaction_distribution(dst_blocks)


if __name__ == "__main__":
    main()


