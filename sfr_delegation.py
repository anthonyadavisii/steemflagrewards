import csv
import json
import os.path

from beem import Steem
from beem.account import Account
from beem.nodelist import NodeList

import sfr_tkn_config as cfg

stm = Steem(node='https://anyx.io')
#nodes = NodeList().get_nodes()
#stm = Steem(node='https://rpc.usesteem.com')
#stm = Steem(node=nodes)
sfr = Account(cfg.SFRACCOUNT, steem_instance=stm)

def loadjson(filename):
    if os.path.exists(filename):
        with open(filename) as json_file:
            loadedfile = json.load(json_file)
    else:
        print(filename+" not found!")
        return
    return loadedfile

last_checked_block = loadjson('last_block.json')
delegations = loadjson('delegations.json')

def get_current_delegation_ops():
    op_list = []
    delegators = []
    last_block = None
    start_block = None
    global last_checked_block
    try:
        if last_checked_block:
            last_block = last_checked_block['block']+1
    except NameError:
        print("Last Checked Block not defined. Must be initial run.")
    for op in sfr.history_reverse(stop=last_block,use_block_num=True,only_ops=["delegate_vesting_shares"]):
        if start_block == None:
            start_block = op['block']
        if op['delegator'] in delegators:
            continue
        op_list.append(op)
        delegators.append(op['delegator'])
    start_block_dict = {'block': start_block or last_block}
    with open('last_block.json', 'w') as json_file:
        json.dump(start_block_dict, json_file)
    return op_list

def get_current_delegators_pct(ops):
    sfr_delegated_SP = stm.vests_to_sp(sfr['received_vesting_shares']['amount'])
    delegator_update_list = []
    consolidated_delegation_list = []
    delegators_w_updates = []
    remove_list = []
    delegator_dict = {}
    global delegations
    try:
        if delegations:
            print("Loaded delegations...")
    except NameError:
        print("Delegations not loaded!")
        delegations = []
    for op in ops:
        Delegated_SP = 0
        if int(op['vesting_shares']['amount']) == 0:
            delegator = op['delegator']             
            remove_list.append(delegator)
        else:
            delegator = op['delegator']
            Delegated_SP = stm.vests_to_sp(float(op['vesting_shares']['amount'][:-6]))
            pct = (Delegated_SP / sfr_delegated_SP) * 100
            delegator_dict = {
                 'delegator': delegator,
                 'Delegated_SP': Delegated_SP,
                 'Percent': pct,
                 }                  
            delegator_update_list.append(delegator_dict)
    try:
        for delegation_update in delegator_update_list:
            delegators_w_updates.append(delegation_update['delegator'])
            consolidated_delegation_list.append(delegation_update)
    except Exception as e:
        print(e)
    print("test")
    try:
        if len(delegations) > 0:
            for delegation in delegations:
                if delegation['delegator'] not in delegators_w_updates and delegation['delegator'] not in remove_list and delegation['delegator'] != 'steemflagrewards':
                    consolidated_delegation_list.append(delegation)
    except Exception as e:
        print(e)
    with open('delegations.json', 'w') as json_file:
        json.dump(consolidated_delegation_list, json_file)
    return consolidated_delegation_list

def update_delegators_w_pct():
    sfr.refresh()
    last_checked_block = loadjson('last_block.json')
    delegations = loadjson('delegations.json')
    dops = get_current_delegation_ops()
    current_delegators_w_pct = get_current_delegators_pct(dops)
    return current_delegators_w_pct