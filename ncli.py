# -*- coding: utf-8 -*-
"""NewChain Command Line Interface.

Usage:
  ncli.py sealer init <name>
  ncli.py sealer start <name>
  ncli.py sealer startall
  ncli.py sealer stopall
  ncli.py sealer clone <source> <target>
  ncli.py sealer batch init <number>
  ncli.py bootnode start
  ncli.py bootnode stop
  ncli.py clean
  ncli.py monitor
  ncli.py (-h | --help)
  ncli.py --version

Options:
  -h --help     Show this screen.
  --version     Show version.

"""
import os
import time
import json
import fnmatch
import subprocess
from docopt import docopt
import monitor

# constants
WORKSPACE = 'devnet'
CMD_GETH = 'bin/geth'
CMD_BOOTNODE = 'bin/bootnode'
CONFIG_NCLI = 'ncli_config.json'
GENESIS_FILE_PATH = 'genesis.json'
CHAIN_ID = '9999'
START_P2P_PORT = 30311
START_RPC_PORT = 8501
BOOTNODE_ENCODE = '943b4e738dfe07d5614fa540eb885c8eb785060fc196357d5b7ceca99de13295ab3d5980a8d8dabcadbcc836ae1e87f1f11c265e7152e3aec834dcc2af40f114'
EXTRA_DATA = "0x0000000000000000000000000000000000000000000000000000000000000000%s0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"

def find_files(pattern, path):
    result = []
    for root, dirs, files in os.walk(path):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                result.append(os.path.join(root, name))
    return result

def get_address_from_keystore(path):
    content = json.loads(open(path).read())
    return content['address']

def update_genesis(address, init_balance='0x200000000000000000000000000000000000000000000000000000000000000'):
    content = json.loads(open(GENESIS_FILE_PATH).read())
    # allocate the balance for given address
    content['alloc'][address] = {'balance': init_balance}
    # add the access control
    config = load_config()
    keys = sorted([v['address'] for k,v in config.items()] + [address])
    content['extraData'] = EXTRA_DATA % ''.join(keys)
    f = open(GENESIS_FILE_PATH, 'w')
    f.write(json.dumps(content, indent=2, sort_keys=True) + "\n")
    f.close()

def clean_genesis():
    content = json.loads(open(GENESIS_FILE_PATH).read())
    content['alloc'] = {}
    content['extraData'] = ''
    f = open(GENESIS_FILE_PATH, 'w')
    f.write(json.dumps(content, indent=2, sort_keys=True) + "\n")
    f.close()

def save_config(config):
    content = json.dumps(config, indent=2, sort_keys=True)
    f = open(CONFIG_NCLI, 'w')
    f.write(content)
    f.close()

def load_config():
    try:
        content = json.loads(open(CONFIG_NCLI).read())
        return content
    except:
        return {}

def init_runtime():
    cmd = 'mkdir -p logs'
    os.system(cmd)
    
def init_sealer(sealer_name, ip_address=None):
    if ip_address:
        print("NotImplemented")
        return
    # load configuration
    config = load_config()
    
    # execute the commands 
    cmd = 'mkdir -p %s/%s' % (WORKSPACE, sealer_name)
    os.system(cmd)
    cmd = 'echo "%s" > %s/%s/password.txt' % (sealer_name, WORKSPACE, sealer_name)
    os.system(cmd)
    cmd = '%s  --datadir %s/%s account new --password "%s/%s/password.txt"' % (CMD_GETH, WORKSPACE, sealer_name, WORKSPACE, sealer_name)
    os.system(cmd)
    # find the keystore address
    files = find_files('UTC-*', '%s/%s/keystore/' % (WORKSPACE, sealer_name))
    #TODO: Add the timestamp compare
    # Only choose first file
    if not files:
        print("Create Sealer Error!")
        return
    address = get_address_from_keystore(files[0])
    update_genesis(address)
    # update configuration
    number_of_sealers = len(config)
    # save configuration
    config[sealer_name] = {
        'p2p_port': START_P2P_PORT + number_of_sealers,
        'rpc_port': START_RPC_PORT + number_of_sealers,
        'address': address,
    }
    save_config(config)
    # Reintialize the all sealers
    for k, v in config.items():
        cmd = 'rm -rf %s/%s/geth*' % (WORKSPACE, k)
        os.system(cmd)
        cmd = '%s --datadir %s/%s/ init %s' % (CMD_GETH, WORKSPACE, k, GENESIS_FILE_PATH)
        os.system(cmd)
    print("Create Sealer `%s`:%s Successfully" % (sealer_name, address))

def clone_sealer(source, target, ip_address=None):
    if ip_address:
        print("NotImplemented")
        return
    # load configuration
    config = load_config()
    
    # execute the commands 
    cmd = 'cp -r %s/%s %s/%s' % (WORKSPACE, source, WORKSPACE, target)
    os.system(cmd)
    # find the keystore address
    files = find_files('UTC-*', '%s/%s/keystore/' % (WORKSPACE, target))
    #TODO: Add the timestamp compare
    # Only choose first file
    if not files:
        print("Create Sealer Error!")
        return
    address = get_address_from_keystore(files[0])
    # update configuration
    number_of_sealers = len(config)
    # save configuration
    config[target] = {
        'p2p_port': START_P2P_PORT + number_of_sealers,
        'rpc_port': START_RPC_PORT + number_of_sealers,
        'address': address,
    }
    save_config(config)
    print("Clone Sealer `%s`:%s Successfully" % (target, address))

def start_sealer(sealer_name, ip_address=None):
    if ip_address:
        print("NotImplemented")
        return
    init_runtime()
    # load configuration
    config = load_config()
    # execute commands
    p2p_port = config[sealer_name]['p2p_port']
    rpc_port = config[sealer_name]['rpc_port']
    address = config[sealer_name]['address']
    cmd = '%s --datadir %s/%s/ --syncmode "full" --port %s --rpc --rpcaddr "localhost" --rpcport %s --rpcapi "personal,db,eth,net,web3,txpool,miner" --bootnodes "enode://%s@127.0.0.1:30310" --networkid %s --gasprice "1" -unlock "0x%s" --password %s/%s/password.txt --mine --targetgaslimit 94000000 2>>logs/geth-%s.log' % (CMD_GETH, WORKSPACE, sealer_name, p2p_port, rpc_port, BOOTNODE_ENCODE, CHAIN_ID, address, WORKSPACE, sealer_name, sealer_name)
    proc = subprocess.Popen([cmd], shell=True)
    pid = proc.pid
    pgid = os.getpgid(pid)
    config[sealer_name]['pgid'] = pgid
    save_config(config)
    print("Start sealer `%s` at pgid:%s, p2p:%s, rpc:%s" % (sealer_name, pgid, p2p_port, rpc_port))

def stop_sealers(ip_address=None):
    if ip_address:
        print("NotImplemented")
        return
    try:
        config = load_config()
        pgids = list(set([v['pgid'] for k,v in config.items()]))
        for pgid in pgids:
            cmd = 'kill -TERM -%s' % pgid
            ret = os.system(cmd)
            if ret == 0:
                print("Stop sealer pgid:%s successfully" % (pgid))
            else:
                print("Stop sealer pgid:%s error!" % (pgid))
    except:
        pass

def start_bootnode(ip_address=None):
    if ip_address:
        print("NotImplemented")
        return
    init_runtime()
    cmd = '%s -nodekey boot.key -verbosity 9 -addr :30310 2>>bootnode.log &' % CMD_BOOTNODE
    ret = os.system(cmd)
    if ret == 0:
        print("Start bootnode successfully")
    else:
        print("Start bootnode error!")

def stop_bootnode(ip_address=None):
    if ip_address:
        print("NotImplemented")
        return
    cmd = 'killall -TERM bootnode'
    ret = os.system(cmd)
    if ret == 0:
        print("Stop bootnode successfully")
    else:
        print("Stop bootnode error!")

def clean_env():
    clean_genesis()
    stop_bootnode()
    stop_sealers()
    cmd = 'rm -rf devnet && rm -f *.log && rm -f ncli_config.json && rm -rf logs'
    os.system(cmd)
    print("Clean OK")

if __name__ == '__main__':
    arguments = docopt(__doc__, version='NCLI 1.0')
    if arguments['sealer'] and arguments['init']:
        if arguments['batch']:
            number_of_sealer = int(arguments['<number>'])
            for i in range(number_of_sealer):
                init_sealer('node%s' % (i + 1))
        else:
            sealer_name = arguments['<name>']
            init_sealer(sealer_name)
    if arguments['sealer'] and arguments['clone']:
        source = arguments['<source>']
        target = arguments['<target>']
        clone_sealer(source, target)
    elif arguments['sealer'] and arguments['startall']:
        config = load_config()
        for k, v in config.items():
            start_sealer(k)
    elif arguments['sealer'] and arguments['start']:
        sealer_name = arguments['<name>']
        start_sealer(sealer_name)
    elif arguments['bootnode'] and arguments['start']:
        start_bootnode()
    elif arguments['clean']:
        clean_env()
    elif arguments['sealer'] and arguments['stopall']:
        stop_sealers()
    elif arguments['bootnode'] and arguments['stop']:
        stop_bootnode()
    elif arguments['monitor']:
        config = load_config()
        monitor.start_monitor(config)

    
    
