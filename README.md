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

***Those prerequisites can be installed by running the install.sh script.***


## Scripts:
### setup_chains.sh
First, this script sets up two Cosmos Gaia blockchains with funded user accounts. Then, it uses ssh to run a set of validator nodes for each of them on remote machines.
After starting the blockchains and synchronizing the nodes it establishes an unordered IBC channel between both blockchains using the Hermes Relayer.

***OBS:*** This file needs to be modified to include the address of the remote machines used for validator nodes. The prerequisites for the blockchains must be installed in all remote machines.

***Usage:*** ./setup_chains.sh -n <NUMBER_OF_NODES> -a <FUNDED_ACCOUNTS> -t [TIMEOUT_COMMIT]

***Options:***   
>  --nodes          | -n&emsp;      Number of consensus nodes to run for each chain.  
  --accounts       | -a&emsp;       Number of funded accounts initialized in the source chain's genesis.  
  --timeout-commit | -t&emsp;       Minimum block interval in seconds (default: 5 seconds).
  
**Example:** ./setup_chains.sh -n 5 -a 10 -t 5

### benchmark.sh:
This script conducts a performance evaluation of cross-chain communication using the previously established IBC channel.
The evaluation workload is composed of cross-chain fungible token transfers (https://github.com/cosmos/ibc/blob/main/spec/app/ics-020-fungible-token-transfer/README.md).
This script must be executed in a machine together with one validator node for each blockchain. This is required to retrieve transaction data through RPC.

***Usage:*** ./benchmark.sh -S <SRC_CHAIN_ADDR> -D <DST_CHAIN_ADDR> -u <NUM_USERS> -t <NUM_TRANSACTIONS> -m <NUM_MESSAGES> -o <OUTPUT_DIR>

***Options:***  
>  -S | --source-addr&emsp;         RPC address of the source chain.  
  -D | --destination-addr&emsp;    RPC address of the destination chain.  
  -u | --users&emsp;               Number of users to be used for submitting transactions.  
  -t | --transactions&emsp;        Number of transactions submitted per user.  
  -m | --messages&emsp;            Number of cross-chain transfer messages inside each transaction (max: 100).  
  -o | --output-dir&emsp;          Directory in which to store benchmark working files.  
  -w | --wait-for-blocks&emsp;     [Optional] Stop waiting for transactions to complete/timeout and start analyzing data after this many empty blocks have been produced in a row (default: 5).  
  --tx-timeout&emsp;               [Optional] Specify how many new blocks can be created before a cross-chain transfer times out (default: 25).  
  --transaction-analysis&emsp;     [Optional] Enables analysis of transaction and IBC message sizes (slower).  
  
***OBS:*** --transaction-analysis is currently unavailable in favor of decreasing the overall time to complete the default benchmarking mode.

***Example:*** ./benchmark.sh -S 'localhost:26657' -D 'localhost:36657' -u 10 -t 25 -m 20 -o 'benchmarking_test'

### Outputs:
The tool generates a file called "benchmarking_report.txt" in the specified output directory. This file contains a performance report generated based on the execution of the specified workload.

