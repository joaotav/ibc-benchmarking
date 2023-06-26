#!/bin/bash

if [ $(id -u) -eq 0 ]; then
	echo "WARNING: running this script with sudo privileges may break the installation"
	exit
fi

# Install gcc, make, curl, c compiler, git, jq
sudo apt-get update
sudo apt-get install -y make gcc curl build-essential libssl-dev git jq

cd ~

# Install golang
command -v go &> /dev/null
if [ $? -ne 0 ]
    then
    echo "Installing Go.."
    sleep 2
    
    wget https://go.dev/dl/go1.17.5.linux-amd64.tar.gz
    sudo tar -C /usr/local -xzf go1.17.5.linux-amd64.tar.gz
    export PATH=$PATH:/usr/local/go/bin
    mkdir -p $HOME/go/bin
    sudo echo "export PATH=$PATH:$(go env GOPATH)/bin" >> ~/.bashrc
    rm go1.17.5.linux-amd64.tar.gz
    source $HOME/.bashrc
    echo
    echo "Done!"
else
    echo  "Go is already installed on your system, skipping installation..."
fi


# Install gaia
git clone -b v7.0.2 https://github.com/cosmos/gaia
cd gaia && make install -j4
source ~/.bashrc

cd ~

# Install rust and cargo
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source $HOME/.cargo/env

# Install hermes
cargo install ibc-relayer-cli -j4 --bin hermes --version 1.0.0 --locked

# Update environment
exec $SHELL
