This repository contains the evaluation tool developed as part of the paper "Analyzing the Performance of the Inter-Blockchain Communication Protocol". This paper has been published at the 53rd Annual IEEE/IFIP International Conference on Dependable Systems and Networks (DSN'23).

A full version is available online: https://arxiv.org/abs/2303.10844

The dataset generated through the experiments discussed in the paper are available online: https://drive.google.com/drive/folders/1f3t4Qf_mC2atcgpafTHk4qv9vWesjfwQ?usp=sharing

## Prerequisites:
### For the blockchains:
- Go v1.17.5
- Cosmos Hub (Gaia) v7.0.2

### For the IBC relayer:
- Rust compiler v1.6.0
- Hermes Relayer v0.15.0 (https://github.com/informalsystems/hermes)

> [!TIP]
> Those prerequisites can be installed by running the install.sh script.


## Scripts:
### setup_chains.sh
First, this script sets up two Cosmos Gaia blockchains with funded user accounts. Then, it uses ssh to run a set of validator nodes for each of them on remote machines.
After starting the blockchains and synchronizing the nodes it establishes an unordered IBC channel between both blockchains using the Hermes Relayer.

> [!IMPORTANT]
> This file needs to be modified to include the address of the remote machines used for validator nodes. The prerequisites for the blockchains must be installed in all remote machines.

 
**Usage:** 
>  ./setup_chains.sh -n <NUMBER_OF_NODES> -a <FUNDED_ACCOUNTS> -t [TIMEOUT_COMMIT]

**Options:** 

```
  --nodes          | -n;      Number of consensus nodes to run for each chain.  
  --accounts       | -a;      Number of funded accounts initialized in the source chain's genesis.  
  --timeout-commit | -t;      Minimum block interval in seconds (default: 5 seconds).
```

**Example:** 
>  ./setup_chains.sh -n 5 -a 10 -t 5

### benchmark.sh:
This script conducts a performance evaluation of cross-chain communication using the previously established IBC channel.
The evaluation workload is composed of cross-chain fungible token transfers (https://github.com/cosmos/ibc/blob/main/spec/app/ics-020-fungible-token-transfer/README.md).
This script must be executed in a machine together with one validator node for each blockchain. This is required to retrieve transaction data through RPC.

**Usage:** 
>  ./benchmark.sh -S <SRC_CHAIN_ADDR> -D <DST_CHAIN_ADDR> -u <NUM_USERS> -t <NUM_TRANSACTIONS> -m <NUM_MESSAGES> -o <OUTPUT_DIR>

**Options:**  
```
  -S | --source-addr;         RPC address of the source chain.  
  -D | --destination-addr;    RPC address of the destination chain.  
  -u | --users;               Number of users to be used for submitting transactions.  
  -t | --transactions;        Number of transactions submitted per user.  
  -m | --messages;            Number of cross-chain transfer messages inside each transaction (max: 100).  
  -o | --output-dir;          Directory in which to store benchmark working files.  
  -w | --wait-for-blocks;     [Optional] Stop waiting for transactions to complete/timeout and start analyzing data after this many empty blocks have been produced in a row (default: 5).  
  --tx-timeout;               [Optional] Specify how many new blocks can be created before a cross-chain transfer times out (default: 25).  
  --transaction-analysis;     [Optional] Enables analysis of transaction and IBC message sizes (slower).  
```  
> [!NOTE]
> The option --transaction-analysis is currently unavailable as it requires additional logic that increases the completion time of default benchmarking mode given the current code structure.

**Example:** 
>  ./benchmark.sh -S 'localhost:26657' -D 'localhost:36657' -u 10 -t 25 -m 20 -o 'benchmarking_test'

## Benchmark output:
The tool generates a file called "benchmarking_report.txt" in the specified output directory. This file contains a performance report generated based on the execution of the specified workload.

### Sample output:

```
[+] Benchmark configuration summary:

 Source chain: blockchain0 
 Destination chain: blockchain1
 Number of validators in each chain: 5
 Number of user accounts: 10
 Transactions submitted per user: 50
 Total number of transactions: 500
 Transfer messages per transaction: 100
 Total number of transfer messages: 50000

 IBC transfers submission (time elapsed): 5m 18s
 Time waiting for empty blocks at the end of benchmark: 0m 1s
 Blockchain data collection (time elapsed): 7m 46s
 Total time elapsed: 13m 5s

----------------------------------------------------------------------
[+] Transaction distribution analysis for blockchain0:

 0 tx(s): 1 block(s)
 10 tx(s): 29 block(s)
 19 tx(s): 1 block(s)
 21 tx(s): 17 block(s)
 23 tx(s): 1 block(s)
 25 tx(s): 1 block(s)
 26 tx(s): 1 block(s)

----------------------------------------------------------------------
[+] Transaction distribution analysis for blockchain1:

 0 tx(s): 26 block(s)
 2 tx(s): 1 block(s)
 9 tx(s): 1 block(s)
 11 tx(s): 20 block(s)
 16 tx(s): 1 block(s)
 17 tx(s): 1 block(s)

----------------------------------------------------------------------
[+] Throughput analysis for chain 'blockchain0':

 Blocks finalized: 51

 Avg. block time: 6.302 seconds
 Number of empty blocks: 1 (1.96%)

 Avg. number of txs per block (counting empty blocks): 14.51
 Avg. number of txs per second(transfer, recv, ack): 2.35

 Avg. number of messages per tx: 97.30
 Avg. number of messages per block (counting empty blocks): 1411.76
 Avg. number of messages per second (transfer, recv, ack, timeout): 228.50
 Avg. number of transfers per second: 158.68


----------------------------------------------------------------------
[+] Throughput analysis for chain 'blockchain1':

 Blocks finalized: 50

 Avg. block time: 6.322 seconds
 Number of empty blocks: 26 (52.00%)

 Avg. number of txs per block (counting empty blocks): 5.28
 Avg. number of txs per second(transfer, recv, ack): 0.85

 Avg. number of messages per tx: 90.91
 Avg. number of messages per block (counting empty blocks): 480.00
 Avg. number of messages per second (transfer, recv, ack, timeout): 77.47
 Avg. number of transfers per second: 0.00


----------------------------------------------------------------------
[+] Round trip time analysis for chains 'blockchain0 -> blockchain1':

 Average round trip time: 178.920s
 Shortest round trip time: 163.744s
 Longest round trip time: 188.840s

----------------------------------------------------------------------
[+] Success rate analysis for channel 'blockchain0 -> blockchain1':

 IBC transfers submitted to 'blockchain0': 50000
 'Transfer' messages committed to 'blockchain0': 50000
 'Receive' messages committed to 'blockchain1': 24000
 'Acknowledgement' messages committed to 'blockchain0': 22000
 'Timeout' messages committed' to 'blockchain0' (source chain): 0

 Transfers completed (transfer, recv, ack): 22000 (44.00%)
 Transfers partially completed (transfer, recv): 2000 (4.00%)
 Transfers only initiated (transfer): 26000 (52.00%)
 Transfers not initiated (submitted but not committed): 0 (0.00%)
 Timed out transfers: 0 (0.00%)

----------------------------------------------------------------------
[+] IBC messages confirmation latency analysis for chains 'blockchain0 -> blockchain1':

 Avg. transfer message confirmation latency: 6.311s
 Shortest transfer latency observed: 5.131s
 Longest transfer latency observed: 7.855s

 Avg. recv message confirmation latency: 12.190s
 Shortest recv message confirmation latency: 6.386s
 Longest recv message confirmation latency: 90.453s

 Avg. acknowledgement message confirmation latency: 8.431s
 Shortest acknowledgement message confirmation latency: 6.208s
 Longest acknowledgement message confirmation latency: 10.349s

----------------------------------------------------------------------
[+] Data analysis for chain 'blockchain0':

 Collective size of all blocks (excl. empty blocks at the end): 37.24 MB
 Avg. block size (excl. empty blocks at the end): 747.81 kB
 Number of transactions committed to the blockchain: 740
 Number of messages committed in the blockchain: 72000

 Number of transactions containing transfer messages on blockchain0: 500
 Number of transfer messages on blockchain0: 50000

 Number of transactions containing recv messages on blockchain0: 0
 Number of recv messages on blockchain0: 0

 Number of transactions containing ack messages on blockchain0: 240
 Number of ack messages on blockchain0: 22000

 Number of transactions containing timeout messages on blockchain0: 0
 Number of timeout messages on blockchain0: 0

----------------------------------------------------------------------
[+] Data analysis for chain 'blockchain1':

 Collective size of all blocks (excl. empty blocks at the end): 30.07 MB
 Avg. block size (excl. empty blocks at the end): 615.79 kB
 Number of transactions committed to the blockchain: 264
 Number of messages committed in the blockchain: 24000

 Number of transactions containing transfer messages on blockchain1: 0
 Number of transfer messages on blockchain1: 0

 Number of transactions containing recv messages on blockchain1: 264
 Number of recv messages on blockchain1: 24000

 Number of transactions containing ack messages on blockchain1: 0
 Number of ack messages on blockchain1: 0

 Number of transactions containing timeout messages on blockchain1: 0
 Number of timeout messages on blockchain1: 0

----------------------------------------------------------------------
```


