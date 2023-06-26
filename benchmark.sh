#!/bin/bash
COMPLETION=""

display_usage() {
  echo -e "$1"
  echo -e "\n Usage: ./$(basename $BASH_SOURCE)  -S <SRC_CHAIN_ADDR> -D <DST_CHAIN_ADDR> -u <NUM_USERS> -t <NUM_TRANSACTIONS> -m <NUM_MESSAGES> -o <OUTPUT_DIR>"
  echo -e "\n Options: \n"
  echo " -S | --source-addr         RPC address of the source chain."
  echo " -D | --destination-addr    RPC address of the destination chain"
  echo " -u | --users               Number of users to be used for submitting transactions."
  echo " -t | --transactions        Number of transactions submitted per user."
  echo " -m | --messages            Number of cross-chain transfer messages inside each transaction (max: 100)."
  echo " -o | --output-dir          Directory in which to store benchmark working files."
  echo " -w | --wait-for-blocks     [Optional] Stop waiting for transactions to complete/timeout and start analyzing data after this many empty blocks have been produced in a row (default: 5)."
  echo " --tx-timeout               [Optional] Specify how many new blocks can be created before a cross-chain transfer times out (default: 25)."
  echo " --transaction-analysis     [Optional] Enables analysis of transaction and IBC message sizes (slower)."
  echo -e "\n Example: ./$(basename $BASH_SOURCE)  -S 'localhost:26657' -D 'localhost:36657' -u 10 -t 25 -m 20 -o 'benchmarking_test' \n"
  exit 1
}



get_current_height() {
    CHAIN_ADDR=$1 # Must differ chains by their addresses, as the --chain-id flag does not work

    HEIGHT=$(gaiad --node "tcp://$CHAIN_ADDR" query block | jq | grep height | awk -F":" 'NR==1{print $2}' | tr -d \"\ \,)
    echo "$HEIGHT"
}


get_chain_id() {
    CHAIN_ADDR=$1

    CHAIN_ID=$(gaiad --node "tcp://$CHAIN_ADDR" query block | jq | grep "chain_id" |  awk -F":" 'NR==1{print $2}' | tr -d \"\ \,)
    echo "$CHAIN_ID"
}

wait_for_empty_blocks(){
# End benchmark when the blockchain produces N empty blocks in a row
    CHAIN_ADDR=$1
    blocks_to_wait=$2
    empty_count=0
    last_height=0
    while :
    do
        height=$(get_current_height "$SRC_CHAIN_ADDR")
        block_data=$(curl -s "$CHAIN_ADDR/blockchain?minHeight=$height&maxHeight=$height")
        num_txs=$(echo -n "$block_data" | jq '.result.block_metas[0].num_txs' | tr -d '"')

        if [ $num_txs -eq 0 ]; then # If the queried block contains 0 transactions

            if [ "$height" -ne "$last_height" ]; then # If it's empty and it's not the last empty height that has already been counted
                let "empty_count+=1"
                last_height="$height"
            fi

        else
            empty_count=0 # If there's a non empty block, reset the count

        fi
    
        if [ $empty_count -ge $blocks_to_wait ]; then
            break
        fi

        sleep 0.5

    done
}

get_relayer_data(){
    SRC_CHAIN_ID=$1
    DST_CHAIN_ID=$2

    # Store log messages about transactions sent to and confirmed in the source chain (Acknowledgements)
    grep $OUTPUT_DIR/hermes_log.txt -e "transactions confirmed" | grep "dst_chain=$SRC_CHAIN_ID" >> $OUTPUT_DIR/logs_$SRC_CHAIN_ID.txt 

    # Store log messages about transaction broadcast and confirmation (Transfers)
    grep -e 'waiting for commit of tx hashes' -e 'wait_for_block_commits' $OUTPUT_DIR/transfer_log.txt >> $OUTPUT_DIR/logs_$SRC_CHAIN_ID.txt

    # Store log messages about transactions sent to and confirmed in the destination chain (Recv messages)
    grep $OUTPUT_DIR/hermes_log.txt -e "transactions confirmed" | grep "dst_chain=$DST_CHAIN_ID" >> $OUTPUT_DIR/logs_$DST_CHAIN_ID.txt 
}


get_block_data() {
    FIRST_BLOCK=$1
    LAST_BLOCK=$2
    CHAIN_ID=$3
    CHAIN_ADDR=$4
    OUTPUT_DIR=$5
    TX_DATA_ANALYSIS=$6

    n_blocks=$(($LAST_BLOCK - $FIRST_BLOCK))

    for (( i=$FIRST_BLOCK; i<=$LAST_BLOCK; i++ )); do 

        block_data=$(curl -s "$CHAIN_ADDR/blockchain?minHeight=$i&maxHeight=$i") # Get JSON block information
        block_height=$(echo -n "$block_data" | jq '.result.block_metas[0].header.height' | tr -d '"')
        block_time=$(echo -n "$block_data" | jq '.result.block_metas[0].header.time')
        block_size=$(echo -n "$block_data" | jq '.result.block_metas[0].block_size' | tr -d '"')
        num_txs=$(echo -n "$block_data" | jq '.result.block_metas[0].num_txs' | tr -d '"')

        if [ "$TX_DATA_ANALYSIS" = "true" ]; then # Perform detailed analysis of transaction and message sizes
            detailed_block_data=$(gaiad --node "tcp://$CHAIN_ADDR" query block $i)
            tx_data=($(echo -n "$detailed_block_data" | jq '.block.data.txs' | tr -d '[],"'))
        fi
                
        # Paginate transactions when above 25 txs to prevent problems due to too much data for the API to handle
        # We need to query each page until we retrieve every tx

        num_pages=$(( ( $num_txs / 1 ) + ( $num_txs % 1 > 0 ) )) # Perform ceiling rounding to know how many pages to query

        tx_hashes=() # Array to store transaction hashes
        
        json_data="{\"chain-id\": \"$CHAIN_ID\", \"block_height\": $block_height, \"block_time\": $block_time,  \"block_size\": $block_size, \"num_transactions\": $num_txs,  \"transactions\": ["
        for (( p=1; p<=num_pages; p++ )); do
            tx_info=$(gaiad --node "tcp://$CHAIN_ADDR" query txs --events tx.height=$i --limit 1 --page $p)
            tx_hash=$(echo "${tx_info}" | grep txhash | awk '{$1=$1;print}' | cut -d ":" -f 2- | tr -d \ \ | paste -sd " " -)

            msg_transfer=$(echo $tx_info | grep -o "'@type': /ibc.applications.transfer.v1.MsgTransfer" | wc -l ) # Get number of MsgTransfer packets
            msg_recv=$(echo $tx_info | grep -o "'@type': /ibc.core.channel.v1.MsgRecvPacket" | wc -l ) # Get number of MsgRecv packets
            msg_ack=$(echo $tx_info | grep -o "'@type': /ibc.core.channel.v1.MsgAcknowledgement" | wc -l ) # Get number of MsgAcknowledgement packets
            msg_timeout=$(echo $tx_info | grep -o "'@type': /ibc.core.channel.v1.MsgTimeout" | wc -l ) # Get number of Timeout messages

            json_data+="{\"tx_hash\": \"${tx_hash}\", "
          #  if [ "$TX_DATA_ANALYSIS" = "true" ]; then
          #      json_data+="\"tx_data\": \"${tx_data[$j]}\", "
          #  fi
            
            json_data+="\"MsgTransfer\": $msg_transfer, "
            json_data+="\"MsgRecvPacket\": $msg_recv, "
            json_data+="\"MsgAcknowledgement\": $msg_ack, "
            json_data+="\"MsgTimeout\": $msg_timeout}"

            if [ $p -lt ${num_pages} ]; then # if it is not the last transaction in the block
                json_data+="," # Add comma to indicate that there's another transaction after the current one
            fi

        done
        
        json_data+="]" # Add bracket to close "transactions"
        json_data+="}"
        tx_hashes="" # Reset variable

        echo $json_data >> $OUTPUT_DIR/block_data_$CHAIN_ID.txt
        loading "[+] Retrieving blockchain data from $CHAIN_ID:" "$(($i - $FIRST_BLOCK ))" "$n_blocks"        
        
        # for (( p=1; p<=num_pages; p++ )); do
        #     tx_hashes+=($( gaiad --node "tcp://$CHAIN_ADDR" query txs --events tx.height=$i --limit 1 --page $p | grep txhash | awk '{$1=$1;print}' | cut -d ":" -f 2- | tr -d \ \ | paste -sd " " - ))
        # done
        
        # json_data="{\"chain-id\": \"$CHAIN_ID\", \"block_height\": $block_height, \"block_time\": $block_time,  \"block_size\": $block_size, \"num_transactions\": $num_txs,  \"transactions\": ["

        # for j in ${!tx_hashes[@]}; do
        #     tx_info=$(gaiad --node "tcp://$CHAIN_ADDR" query tx "${tx_hashes[$j]}") # Query individual txs to get messages information

        #     msg_transfer=$(echo $tx_info | grep -o "'@type': /ibc.applications.transfer.v1.MsgTransfer" | wc -l ) # Get number of MsgTransfer packets
        #     msg_recv=$(echo $tx_info | grep -o "'@type': /ibc.core.channel.v1.MsgRecvPacket" | wc -l ) # Get number of MsgRecv packets
        #     msg_ack=$(echo $tx_info | grep -o "'@type': /ibc.core.channel.v1.MsgAcknowledgement" | wc -l ) # Get number of MsgAcknowledgement packets
        #     msg_timeout=$(echo $tx_info | grep -o "'@type': /ibc.core.channel.v1.MsgTimeout" | wc -l ) # Get number of Timeout messages

        #     json_data+="{\"tx_hash\": \"${tx_hashes[$j]}\", "
        #     if [ "$TX_DATA_ANALYSIS" = "true" ]; then
        #         json_data+="\"tx_data\": \"${tx_data[$j]}\", "
        #     fi
            
        #     json_data+="\"MsgTransfer\": $msg_transfer, "
        #     json_data+="\"MsgRecvPacket\": $msg_recv, "
        #     json_data+="\"MsgAcknowledgement\": $msg_ack, "
        #     json_data+="\"MsgTimeout\": $msg_timeout}"

        #     if [ $j -lt $(( ${#tx_hashes[@]} - 1 )) ]; then # if it is not the last transaction in the block
        #         json_data+="," # Add comma to indicate that there's another transaction after the current one
        #     fi

        # done

        # json_data+="]" # Add bracket to close "transactions"
        # json_data+="}"
        # tx_hashes="" # Reset variable

        # #echo $block_data >> $OUTPUT_DIR/raw_block_data_$CHAIN_ID.txt # Write block data to file
        # echo $json_data >> $OUTPUT_DIR/block_data_$CHAIN_ID.txt
        # loading "[+] Retrieving blockchain data from $CHAIN_ID:" "$(($i - $FIRST_BLOCK ))" "$n_blocks"

    done
    echo
}


clear_data() {
    # Clear blockchain and transaction data stored in $OUTPUT_DIR
    OUTPUT_DIR=$1
    CHAIN_ID=$2
    rm $OUTPUT_DIR/hermes_log.txt > /dev/null 2>&1
    rm $OUTPUT_DIR/transfer_log.txt > /dev/null 2>&1
    #rm $OUTPUT_DIR/block_data_${CHAIN_ID}.txt > /dev/null 2>&1
    rm $OUTPUT_DIR/logs_${CHAIN_ID}.txt > /dev/null 2>&1
}


clear_previous_data() {   
    OUTPUT_DIR=$1
    if [ -d "$OUTPUT_DIR" ] 
    then # Directory exists 
        if [ -z "$(ls -A $OUTPUT_DIR/)" ] # Directory is empty
        then
            return 1 # Continue execution
        else # Ask if the user wants to overwrite files in the directory
            echo "[+] Directory '$OUTPUT_DIR/' exists and is not empty."
            read -p "[+] Proceeding will write to this directory. Proceed? [y/n] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]
            then
                return 1 # (OK) Overwrite, continue execution
            else
                return 0 # (NOK) User declined overwrite, stop execution
            fi
        fi
    else
        return 1
    fi
}


display_elapsed_time() {
    TASK=$1
    TASK_TIME=$2
    echo -e "\n[+] $TASK completed!"

    if [ $TASK_TIME -lt 3600 ]; then 
        echo "[+] Task duration: $(($TASK_TIME / 60))m $(($TASK_TIME % 60))s"
    else
        echo "[+] Task duration: $(($TASK_TIME / 3600))h $(($TASK_TIME % 3600 / 60))m $(($TASK_TIME % 3600 % 60))s"
    fi

    if [ $SECONDS -lt 3600 ]; then
        echo -e "[+] Total time elapsed: $(($SECONDS / 60))m $(($SECONDS % 60))s \n"
    else
       echo -e "[+] Total time elapsed: $(($SECONDS / 3600))h $(($SECONDS % 3600 / 60))m $(($SECONDS % 3600 % 60))s \n"
    fi
}
                          
loading() {
    text=$1
    progress=$2
    total=$3
    percentage=$(( $progress * 100 / $total ))
    echo -ne "\r\033[K$text [$percentage%]"
}

display_loading() {
  pid=$!
  text=$1
  echo -ne "$text\r"

  while kill -0 $pid 2>/dev/null; do
    echo -ne "$text\r"
    sleep 0.5
    echo -ne "$text.\r"
    sleep 0.5
    echo -ne "$text..\r"
    sleep 0.5
    echo -ne "$text...\r"
    sleep 0.5
    echo -ne "\r\033[K"
    echo -ne "$text\r"
    sleep 0.2
  done
  echo -e "$text\n[+] Done!\n"
}

submit_txs() {
    USER_NUM=$1
    N_TRANSACTIONS=$2
    N_MESSAGES=$3 
    OUTPUT_DIR=$4
    TX_TIMEOUT=$5
for (( i=1; i<=$N_TRANSACTIONS; i++ ));
do
    hermes --config hermes_config.toml tx ft-transfer --dst-chain blockchain1 --src-chain blockchain0 --src-port transfer --src-channel channel-0 --amount 1 --denom "coins" --number-msgs $N_MESSAGES --timeout-height-offset $TX_TIMEOUT  --key-name "user$USER_NUM" >> $OUTPUT_DIR/transfer_log.txt 2>&1
    #loading "[+] Submitting IBC transfers to source blockchain..." "$(( $(($i * $N_USERS)) - $(($N_USERS - $j)) ))" "$(($N_TRANSACTIONS * $N_USERS))" 
done
}


trap quit SIGTERM

# Whether to analyze transaction data in detail or not 
TX_DATA_ANALYSIS="false" 

# How many empty blocks need to be generated in a row before the benchmarking ends. Longer
# intervals allow the blockchain to commit more messages if they have been delayed
# during processing
BLOCKS_TO_WAIT=5 

# Number of blocks that can be created before an IBC transfer times out
TX_TIMEOUT=50

# Check and assign argument values
while [[ $# -gt 0 ]]; do
  case $1 in
    -S|--source-addr)
      SRC_CHAIN_ADDR="$2"
      shift # shift argument
      shift # shift value
      ;;
    -D|--destination-addr)
      DST_CHAIN_ADDR="$2"
      shift 
      shift 
      ;;
    -u|--users)
      N_USERS="$2"
      shift
      shift
      ;;
    -t|--transactions)
      N_TRANSACTIONS="$2"
      shift
      shift
      ;;
    -m|--messages)
      N_MESSAGES="$2"
      shift
      shift
      ;;
    -o|--output-dir)
      OUTPUT_DIR="$2"
      shift
      shift
      ;;
    -w|--wait-for-blocks)
      BLOCKS_TO_WAIT="$2"
      shift
      shift
      ;;
    --transaction-analysis)
      TX_DATA_ANALYSIS="true"
      shift
      ;;
    --tx-timeout)
      TX_TIMEOUT="$2"
      shift
      shift
      ;;
   -h|--help)
      display_usage
      ;;
    -*|--*)
      echo " Unknown option $1"
      display_usage
      exit 1
      ;;
     *)
      display_usage
      exit 1
      ;;
  esac
done

  
if [[ -z "$SRC_CHAIN_ADDR" || -z "$DST_CHAIN_ADDR" || -z "$N_USERS" || -z "$N_TRANSACTIONS" || -z "$N_MESSAGES" || -z "$OUTPUT_DIR" ]]; then
  display_usage " Missing required parameter. Please check if all parameters were specified.\n"
  exit 1
fi

SRC_CHAIN_ID=$(get_chain_id "$SRC_CHAIN_ADDR")
DST_CHAIN_ID=$(get_chain_id "$DST_CHAIN_ADDR")


if (clear_previous_data "$OUTPUT_DIR") 
then
    echo "[+] User declined overwrite. Quitting..."
    exit 1
fi

clear_data "$OUTPUT_DIR" "$SRC_CHAIN_ID"
clear_data "$OUTPUT_DIR" "$DST_CHAIN_ID"


# Create directory for output files or use if already existing
if ! mkdir -p $OUTPUT_DIR 2>/dev/null
then
    echo "Failed to create folder for output files. Aborting..."
    exit 1
fi


# Increase number of max connections to allow for multiple processes submitting IBC transactions through the relayer
ulimit -Sn 16384

# Start hermes relayer
hermes --config hermes_config.toml start &> $OUTPUT_DIR/hermes_log.txt &

echo "[+] Initializing benchmark..."

START=`date +%s.%N`

SECONDS=0

sleep 60

clear
    
SRC_FIRST_BLOCK=$(( $(get_current_height "$SRC_CHAIN_ADDR")  + 1 ))
DST_FIRST_BLOCK=$(( $(get_current_height "$DST_CHAIN_ADDR")  + 1 ))

TRANSFERS_TIME=$SECONDS


for (( j=1; j<=$N_USERS; j++ ));
do
    submit_txs "$j" "$N_TRANSACTIONS" "$N_MESSAGES" "$OUTPUT_DIR" "$TX_TIMEOUT" &
    user_pids[${i}]=$!
done

echo "[+] Submitting and confirming transactions..."
echo

for user_pid in ${user_pids[*]}; do
    wait $user_pid
done
echo


TRANSFERS_TIME=$(( $SECONDS - $TRANSFERS_TIME )) # How long it took to submit all the transfers to the source chain

# Since we are testing the performance of the system, finish submitting transactions
# and wait until the next block (or 2) are generated, this will let us know the throughput
# of the system 

BLOCK_WAITING_TIME=$SECONDS

SRC_LAST_TPUT_BLOCK=$(( $(get_current_height "$SRC_CHAIN_ADDR")  + 1 ))
DST_LAST_TPUT_BLOCK=$(( $(get_current_height "$DST_CHAIN_ADDR")  + 1 ))

echo "[+] Waiting for $BLOCKS_TO_WAIT empty blocks to be generated..."

wait_for_empty_blocks "$SRC_CHAIN_ADDR" "$BLOCKS_TO_WAIT"


BLOCK_WAITING_TIME=$(( $SECONDS - $BLOCK_WAITING_TIME ))

SRC_LAST_BLOCK=$(get_current_height "$SRC_CHAIN_ADDR")
DST_LAST_BLOCK=$(get_current_height "$DST_CHAIN_ADDR")

# Stop running relayer processes
killall hermes &> /dev/null 2>&1

# Display summary of benchmarking
display_elapsed_time "Transfers" "$TRANSFERS_TIME"

echo "[+] Source chain ($SRC_CHAIN_ID):"
echo "[+] First block: $SRC_FIRST_BLOCK"
echo -e "[+] Last block: $SRC_LAST_BLOCK\n"
echo "[+] Destination chain ($DST_CHAIN_ID):"
echo "[+] First block: $DST_FIRST_BLOCK"
echo -e "[+] Last block: $DST_LAST_BLOCK\n"


DATA_COLLECTION_TIME=$SECONDS

# Get data for source chain
get_block_data "$SRC_FIRST_BLOCK" "$SRC_LAST_BLOCK" "$SRC_CHAIN_ID" "$SRC_CHAIN_ADDR" "$OUTPUT_DIR" "$TX_DATA_ANALYSIS"

# Get data for destination chain
get_block_data "$DST_FIRST_BLOCK" "$DST_LAST_BLOCK" "$DST_CHAIN_ID" "$DST_CHAIN_ADDR" "$OUTPUT_DIR" "$TX_DATA_ANALYSIS"

get_relayer_data "$SRC_CHAIN_ID" "$DST_CHAIN_ID"

DATA_COLLECTION_TIME=$(( $SECONDS - $DATA_COLLECTION_TIME ))

display_elapsed_time "Data collection" "$DATA_COLLECTION_TIME"

DATA_ANALYSIS_TIME=$SECONDS

python3 data_analysis.py "$OUTPUT_DIR" "$SRC_CHAIN_ID" "$DST_CHAIN_ID" "$SRC_CHAIN_ADDR" "$N_USERS" "$N_TRANSACTIONS" "$N_MESSAGES" "$TX_DATA_ANALYSIS" "$TRANSFERS_TIME" "$BLOCK_WAITING_TIME" "$DATA_COLLECTION_TIME" "$SRC_LAST_TPUT_BLOCK" "$DST_LAST_TPUT_BLOCK"

DATA_ANALYSIS_TIME=$(( $SECONDS - $DATA_ANALYSIS_TIME ))

display_elapsed_time "Data analysis" "$DATA_ANALYSIS_TIME"

#clear_data "$OUTPUT_DIR" "$SRC_CHAIN_ID"
#clear_data "$OUTPUT_DIR" "$DST_CHAIN_ID"
