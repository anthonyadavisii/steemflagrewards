import asyncio
import csv
import datetime
import discord
import logging
import os
import sqlite3
import urllib.request

from beem import Steem
from beem.account import Account
from beem.comment import Comment
from beem.exceptions import AccountDoesNotExistsException, ContentDoesNotExistsException, VotingInvalidOnArchivedPost
from beem.instance import set_shared_steem_instance
from beem.nodelist import NodeList
from beem.utils import construct_authorperm, addTzInfo
from collections import defaultdict
from discord.ext.commands import Bot

import matplotlib.pyplot as plt #for future use
import sfr_config as cfg

import sfr_config as cfg

class RangeDict(dict):
    def __getitem__(self, item):
        if type(item) != range:
            for key in self:
                if item in key:
                    return self[key]
        else:
            return super().__getitem__(item)

class_rank_dict = RangeDict({range(0,999999): 'F0 < 1 Mil',
                             range(1000000,9999999): 'F1 1 Mil', 
                             range(10000000,99999999): 'F2 10 Mil',
                             range(100000000,999999999): 'F3 100 Mil',
                             range(1000000000,9999999999): 'F4 1 Bil',
                             range(10000000000,99999999999): 'F5 10 Bil',
                             range(100000000000,999999999999): 'F6 100 Bil',
                             range(1000000000000,9999999999999): 'F7 1 Tril',
                             range(10000000000000,99999999999999): 'F8 10 Tril',
                             range(100000000000000,999999999999999): 'F9 100 Tril',
                             range(100000000000000,999999999999999): 'F10 1 Quad',
                             range(1000000000000000,9999999999999999): 'F11 10 Quad',
                             range(100000000000000000,999999999999999999): 'F12 100 Quad'}) 

class_img_dict = RangeDict({range(0,999999): 'https://steemitimages.com/DQmT2Q3aRu5maDffFPfU3k3D1xmBrYBLxVWzRtgFZbQ916W/image.png',
                            range(1000000,999999): 'https://steemitimages.com/DQmZc3NgQAy9XByJW8fyJURwUHGpQ6ZqP2v1YZzcnDnR3ig/image.png', 
                            range(10000000,99999999): 'https://steemitimages.com/DQmR3SWn1Js31cvbU4XrLvGbihkasnzfestJpSfyQcHqTEf/image.png',
                            range(100000000,999999999): 'https://steemitimages.com/DQmPL9ZuLMniaTe5YNbd9TZYhSxa2WepDCKi4yNaXBiDaER/image.png',
                            range(1000000000,9999999999): 'https://steemitimages.com/DQmdQyp3F8EMQBpfv9ePAhMyWmD2Fh2AwvjnJLMeB3c9k3B/image.png',
                            range(10000000000,99999999999): 'https://steemitimages.com/DQma3KW2DP9AGAgnjJkXaSBgwHMWuUdV4A3Q9S5QX6ajgyH/image.png',
                            range(100000000000,999999999999): 'https://steemitimages.com/DQmWMzENVRgXHbSxNqmMvWk4hzSesnS2W6K4RWe4qVZaeym/image.png',
                            range(1000000000000,9999999999999): 'https://steemitimages.com/DQmaPHtsmhTLLk7nGw63nGA42Y2wP3uKwNdBoFHYMvvbCsk/image.png',
                            range(10000000000000,99999999999999): 'https://steemitimages.com/DQmV6NhpSJ12hJeRi7eCQ687dUq5FybZQPeFJqcDRyt19ER/image.png',
                            range(100000000000000,999999999999999): 'https://steemitimages.com/DQmQN9VJDNH9c58YFVmUTYNGHZdBbx2J38nGA1ZXSYBzuro/image.png',
                            range(1000000000000000,9999999999999999): 'https://steemitimages.com/DQmcrEMSQKRC6r2kAgyFwSGwL9nfJXgxqnTpCfovpajjg3B/image.png',
                            range(10000000000000000,99999999999999999): 'https://steemitimages.com/DQmPPoYqJNETGBUMyCvVYatMr9WqzEPo7cSp4tnTx71UunM/image.png',
                            range(100000000000000000,999999999999999999): 'https://steemitimages.com/DQmT8RoG7psGKdgXRiU7aWSDRgEMzFZtftqGPge5oGmb2KL/image.png'})


logging.basicConfig(level=logging.INFO, filename=cfg.LOGFILE)

db = sqlite3.connect(cfg.DATABASEFILE)
cursor = db.cursor()

nodes = NodeList().get_nodes()
stm = Steem(node=nodes)
set_shared_steem_instance(stm)
queueing = False

##################################################
# Uncomment for the initial setup of the database
# cursor.execute('''CREATE TABLE steemflagrewards
# (flagger TEXT, comment TEXT, post TEXT, category TEXT, created TEXT, included BOOL, payout REAL, queue BOOL, weight REAL, followon BOOL, dust BOOL default '0', approved_by TEXT, mod_included BOOL, flag_rshares INTEGER)''')
# cursor.execute('CREATE TABLE flaggers (name TEXT)')
# cursor.execute('CREATE TABLE sdl (name TEXT, created TEXT, delegation BOOL)')
# cursor.execute('CREATE TABLE sfr_posts (post TEXT, created TEXT)')
# db.commit()
##################################################
# Uncomment for initial setup of Plotly credential file using env variable
# plotly.tools.set_credentials_file(username=cfg.plotlyuser, api_key=os.getenv('PLOTLY'))
##################################################

def get_abuse_categories(comment_body):
    """Returning the matching categories of abuse"""
    cats = []
    body = comment_body.lower()
    for cat in sorted(cfg.CATEGORIES.keys()):
        if cat in body:
            # distinguish between the overlapping categories "spam"
            # and "comment spam"
            if cat == 'spam' and 'comment spam' in body:
                continue
            cats.append(cat)
    return cats

def get_approval_comment_body(flagger, abuse_categories, dust=False):
    """ assemble the body for the flag approval comment """
    cat_string = ''
    try:
        cat_string = ''.join([cfg.CATEGORIES[cat] for cat in abuse_categories])
    except KeyError:
        print('Key error grabbing category with '+str(abuse_categories))
        logging.info('Key error grabbing category with '+str(abuse_categories))
    if dust is True:
        body = 'Steem Flag Rewards mention comment has been approved ' \
               'for flagger beneficiary post rewards! ' \
               'Thank you for reporting this abuse, @{}.\n{}\n\n' \
               'This post was submitted via our Discord Community channel. ' \
               'Check us out on the following link!\n[SFR Discord]({})'.format(
                   flagger, cat_string, cfg.DISCORD_INVITE)
    else:
        body = 'Steem Flag Rewards mention comment has been approved! ' \
               'Thank you for reporting this abuse, @{}.\n{}\n\n' \
               'This post was submitted via our Discord Community channel. ' \
               'Check us out on the following link!\n[SFR Discord]({})'.format(
                   flagger, cat_string, cfg.DISCORD_INVITE)
    return body

def get_rewards_chart(removed, remaining):
    labels = ['Rewards Removed','Rewards Remaining']
    values = [removed,remaining]
    trace = go.Pie(labels=labels, values=values) #create pie chart
    try:
        charturl = py.plot([trace], filename='flagger_pie_chart_'+str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M")), auto_open=True) #upload pie chart
    except Exception as e:
        print("Chart error")
        print(e)
        return
    charturl += ".png"
    return charturl

def get_wait_time(account):
    """Get the time (in seconds) required until the next comment can be posted.
    Only works for one 'queued' comment.
    """
    account.refresh()
    last_post_timedelta = addTzInfo(datetime.datetime.utcnow()) - account['last_post']
    return max(0, cfg.STEEM_MIN_REPLY_INTERVAL - last_post_timedelta.total_seconds())

def build_mod_report_body(flag_table):
    """ assemble the 8-flagges report post body """
    body = '## This post triggers once the SteemFlagRewards Moderation Team Reviews and Approves 50 ' \
           'flag mention comments via the SteemFlagRewards Abuse Fighting Community on our ' \
           '[Discord]({})\n\nhttps://cdn.steemitimages.com/' \
           'DQmfREGg6Kr1vVi6sbM711ZfahMmb8FpzTWJvDbM7oLmTjW/sfr-mod-fund-steemseph.jpg\n\n' \
           'Moderators have been designated as post beneficiaries based on # of approvals.' \
           ' Our mods have put in a lot of charitable work and effort ' \
           'to enrich the blockchain by reviewing flags. ' \
           ' Please, consider following this account to track this activity \n' \
           'and help reward it accordingly. Feel free to review the flags for ' \
           'quality and let us know how we are doing! \n' \
           '### Would you like to delegate to the Steem Flag Rewards project ' \
           'and promote decentralized moderation? ' \
           'Here are some handy delegation links!\n'.format(cfg.DISCORD_INVITE)
    for amount in [50, 100, 500, 1000]:
        body += " [{} SP](https://steemconnect.com/sign/" \
                "delegateVestingShares?delegator=&" \
                "delegatee={}&vesting_shares=" \
                "{}%20SP)".format(amount, cfg.SFRACCOUNT, amount)
    if len(cfg.WITNESSES):
        body += '\n\nThe following witnesses are providing significant delegations to support the SFR mission. ' \
                'Please consider giving them your vote for witness. ' \
                'Steemconnect links included for convenience.\n'
        for wtn in cfg.WITNESSES:
            body += "* [{}](https://v2.steemconnect.com/sign/account-" \
                    "witness-vote?witness={}&approve=1)\n".format(wtn, wtn)
    if len(cfg.OTHERWITNESS):
        body += '\n\nThe following witnesses have shown considerable support and dedication against abuse. ' \
                'Please consider giving them your vote for witness. ' \
                'Steemconnect links included for convenience.\n'
        for wtn in cfg.OTHERWITNESS:
            body += "* [{}](https://v2.steemconnect.com/sign/account-" \
                    "witness-vote?witness={}&approve=1)\n".format(wtn, wtn)
    if len(cfg.SUPPORTERS):
        list_of_supporters = ", ".join(["@{}".format(user) for user in
                                        cfg.SUPPORTERS])
        body += '\n\nThe following have shown considerable support and / or dedication to the cause and ' \
                'deserve a mention. Check out their blogs if you have the ' \
                'opportunity!\n{}'.format(list_of_supporters)
    body += '\n\n\n{}'.format(flag_table)
    body += '\n\n\n <hr><div class="pull-left"><a href="https://discordapp.com/invite/fmE7Q9q"></a></div> If you feel you\'ve been wrongly flagged, check out @freezepeach, the flag abuse neutralizer. See the <a href="https://steemit.com/introduceyourself/@freezepeach/freezepeach-the-flag-abuse-neutralizer">intro post</a> for more details, or join the <a href="https://discordapp.com/invite/fmE7Q9q">discord server.</a><hr>'
    return body

def build_report_body(flag_table):
    """ assemble the 8-flagges report post body """
    body = '## This post triggers once we have approved flags from 8 distinct ' \
           'flaggers via the SteemFlagRewards Abuse Fighting Community on our ' \
           '[Discord]({})\n\nhttps://steemitimages.com/' \
           'DQmTJj2SXdXcYLh3gtsziSEUXH6WP43UG6Ltoq9EZyWjQeb/frpaccount.jpg\n\n' \
           'Flaggers have been designated as post beneficiaries. Our goal is ' \
           'to empower abuse fighting plankton and minnows and promote a ' \
           'Steem that is less-friendly to abuse. It is simple. Building ' \
           'abuse fighters equals less abuse.\n'\
           '### Would you like to delegate to the Steem Flag Rewards project ' \
           'and promote decentralized moderation? ' \
           'Here are some handy delegation links!\n'.format(cfg.DISCORD_INVITE)
    for amount in [50, 100, 500, 1000]:
        body += " [{} SP](https://steemconnect.com/sign/" \
                "delegateVestingShares?delegator=&" \
                "delegatee={}&vesting_shares=" \
                "{}%20SP)".format(amount, cfg.SFRACCOUNT, amount)
    if len(cfg.WITNESSES):
        body += '\n\nThe following witnesses are providing significant delegations to support the SFR mission. ' \
                'Please consider giving them your vote for witness. ' \
                'Steemconnect links included for convenience.\n'
        for wtn in cfg.WITNESSES:
            body += "* [{}](https://v2.steemconnect.com/sign/account-" \
                    "witness-vote?witness={}&approve=1)\n".format(wtn, wtn)
    if len(cfg.OTHERWITNESS):
        body += '\n\nThe following witnesses have shown considerable support and dedication against abuse. ' \
                'Please consider giving them your vote for witness. ' \
                'Steemconnect links included for convenience.\n'
        for wtn in cfg.OTHERWITNESS:
            body += "* [{}](https://v2.steemconnect.com/sign/account-" \
                    "witness-vote?witness={}&approve=1)\n".format(wtn, wtn)
    if len(cfg.SUPPORTERS):
        list_of_supporters = ", ".join(["@{}".format(user) for user in
                                        cfg.SUPPORTERS])
        body += '\n\nThe following have shown considerable support and / or dedication to the cause and ' \
                'deserve a mention. Check out their blogs if you have the ' \
                'opportunity!\n{}'.format(list_of_supporters)
    body += '\n\n\n{}'.format(flag_table)
    body += '\n\n\n <hr><div class="pull-left"><a href="https://discordapp.com/invite/fmE7Q9q"></a></div> If you feel you\'ve been wrongly flagged, check out @freezepeach, the flag abuse neutralizer. See the <a href="https://steemit.com/introduceyourself/@freezepeach/freezepeach-the-flag-abuse-neutralizer">intro post</a> for more details, or join the <a href="https://discordapp.com/invite/fmE7Q9q">discord server.</a><hr>' #<img src="https://steemitimages.com/DQmNQmR2sgebuWg4pZgPyLEVD5DqtS5VjpZDhkxQya6wf4a/freezepeach-icon.png">
    return body

def flag_leaderboard():
    rank_list = []
    rank_dict = {}
    rank_markdown = ''
    sql = cursor.execute('SELECT flagger, sum(flag_rshares), count(flag_rshares) FROM steemflagrewards GROUP BY flagger ORDER BY sum(flag_rshares) ASC LIMIT 20')
    for q in sql.fetchall():
        sbd_amount = stm.rshares_to_sbd(abs(q[1]))
        rank_list.append({
                                'Downvoter': q[0],
                                'Total Flags': q[2],
                                'rshares': q[1],
                                'sbd_amount': round(sbd_amount,3),
                                'Rank': class_rank_dict[abs(q[1])],
                                'Image': class_img_dict[abs(q[1])]
                            })
    export_csv('sfr',rank_list)
    rank_list = sorted(rank_list, key=lambda k: k['rshares'],reverse=False)
    rank_markdown += '\n # SFR Leaderboard \n'
    rank_markdown += '|Flagger|SBD Amount|Rank|Image|\n|:-----------:|:---------:|:--------|:--------:|'
    for leader in rank_list:
        rank_markdown += '\n|{}|{}|{}|{}|'.format(leader['Downvoter'],str(leader['sbd_amount'])+" SBD", leader['Rank'], leader['Image'])
    return rank_markdown

def export_csv(name,votelist):
    cwd = os.getcwd()
    filename=datetime.datetime.now().strftime(name+"%Y%m%d-%H%M%S.csv")
    keys = votelist[0].keys()
    outfile=open(cwd+'/'+filename,'w')
    writer=csv.DictWriter(outfile, keys)
    writer.writeheader()
    writer.writerows(votelist)

def mod_report():
    """Posting a mod report post with the moderators set as beneficiaries."""
    sql_list = []
    flagged_post_data = []
    sql = cursor.execute(
        "SELECT CASE WHEN category LIKE '%nsfw%' OR category LIKE '%porn spam%' THEN '[NSFW link](https://steemit.com/' || post || '#' || comment || ')' " \
        "ELSE '[Comment](https://steemit.com/\' || post || '#' || comment || ')' END, '@' || approved_by, category, post, comment, " \
        "CASE WHEN category LIKE '%nsfw%' OR category LIKE '%porn spam%' THEN '[NSFW link](https://steemit.com/' || post || ')' " \
        "ELSE '[Comment](https://steemit.com/\' || post || ')' END " \
        "FROM steemflagrewards WHERE mod_included == 0 AND approved_by IN (SELECT approved_by FROM steemflagrewards WHERE mod_included == 0 LIMIT 8)" \
        "LIMIT 50;")
    table = '|Link|Rewards Remaining|Category|\n|:----|:----------------:|:--------|'
    for q in sql.fetchall():
        flagged_post_dict = {}
        try:
            flagged_comment = Comment(q[3])
            pending_payout = flagged_comment['pending_payout_value']
        except Exception as e:
            print('Was unable to obtain pending payout value on https://steemit.com/'+str(q[3]))
            logging.exception(e)
            pending_payout = "Null"
        sql_list.append(q)
        flagged_post_dict = {'link': q[5], 'payout': pending_payout.amount, 'category': q[2]}
        flagged_post_data.append(flagged_post_dict)
    flagged_post_data = sorted(flagged_post_data, key=lambda k: k['payout'],reverse=True)
    flagged_post_data = [dict(tupleized) for tupleized in set(tuple(item.items()) for item in flagged_post_data)]
    for fpd in flagged_post_data:
        if fpd['payout'] >0:
            table += '\n|{}|{}|{}|'.format(fpd['link'],str(fpd['payout'])+" SBD", fpd['category'])
    table += '\n --- \n'
    table1 = '|Link|Approved By|Category|\n|:-----------|:---------------:|:--------|'
    for q in sql_list:
        table1 += '\n|{}|{}|{}|'.format(q[0], q[1], q[2])
    body = build_mod_report_body(table)
    body += '\n\n\n{}'.format(table1)
    sql = cursor.execute(
        "SELECT sum(flag_rshares), sum(payout) FROM (SELECT flag_rshares, payout FROM steemflagrewards WHERE mod_included == 0 AND " \
        "approved_by IN (SELECT approved_by FROM steemflagrewards WHERE mod_included == 0 LIMIT 8) LIMIT 50)")
    q = sql.fetchone()
    removed = stm.rshares_to_sbd(float(q[0]))
    remain = q[1]
    body += "\n --- "
    try:
        body += get_rewards_chart(abs(removed),abs(remain))
    except Exception as e:
        print(e)
    success_ratio = round((abs(removed)/(abs(remain)+abs(removed))*100),2)
    if(success_ratio >= 70):
        body +="\n# Mission Accomplished! \n"
        body +=" http://img200.imageshack.us/img200/3750/missionaccomplishedl.jpg "
    else:
        body +="\n# Mission Failed! \n"
        body +=" https://static.giantbomb.com/uploads/original/0/329/1195180-psd3d036.jpg "
    body += "Reward removal at: "+str(success_ratio)+" % \n"
    body += '\n\n\n <hr><div class="pull-left"><a href="https://discordapp.com/invite/fmE7Q9q"></a></div> If you feel you\'ve been wrongly flagged, check out @freezepeach, the flag abuse neutralizer. See the <a href="https://steemit.com/introduceyourself/@freezepeach/freezepeach-the-flag-abuse-neutralizer">intro post</a> for more details, or join the <a href="https://discordapp.com/invite/fmE7Q9q">discord server.</a><hr>'
    logging.info('Generated post body')
    benlist = []
    approvals = []
    approvers = []
    for q in sql_list:
        approvals.append(str(q[1]).replace('@',''))#extracts username from tuple
    approvers = set(approvals)
    for approver in approvers:
        benlist.append({'account': approver, 'weight': int(approvals.count(approver)/len(approvals)*9900)})
    benlist= sorted(benlist, key=lambda k: k['account'],reverse=False) 
    rep = stm.post(
        'Steem Flag Rewards Mod Report - Moderator Post - {}'.format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M")),
        body, 'sfr-mod-fund', tags=['steemflagrewards', 'abuse', 'steem', 'flag', 'busy'], beneficiaries=benlist,
        parse_body=True, self_vote=False, community='busy', app='busy/2.5.6')
    for s in sql_list:
        query = cursor.execute('UPDATE steemflagrewards SET mod_included = 1 WHERE comment == ?',(s[4],))
    db.commit()
    return construct_authorperm(rep['operations'][0][1])

def report():
    """Posting a report post with the flaggers set as beneficiaries."""
    sql_list = []
    flagged_post_data = []
    cursor.execute('DELETE FROM flaggers;')
    cursor.execute(
        'INSERT INTO flaggers SELECT DISTINCT flagger FROM steemflagrewards WHERE included == 0 ORDER BY created ASC LIMIT 8;')
    sql = cursor.execute(
        "SELECT CASE WHEN category LIKE '%nsfw%' OR category LIKE '%porn spam%' THEN '[NSFW link](https://steemit.com/' || post || '#' || comment || ')' " \
        "ELSE '[Comment](https://steemit.com/\' || post || '#' || comment || ')' END, '@' || flagger, category, post, comment, " \
        "CASE WHEN category LIKE '%nsfw%' OR category LIKE '%porn spam%' THEN '[NSFW link](https://steemit.com/' || post || ')' " \
        "ELSE '[Comment](https://steemit.com/\' || post || ')' END " \
        "FROM steemflagrewards WHERE included == 0 AND flagger IN flaggers;")
    db.commit()
    table = '### Flaggable Posts \n |Link|Rewards Remaining|Category|\n|:----|:------------|:--------|'
    for q in sql.fetchall():
        flagged_post_dict = {}
        flag_list = []
        try:
            flagged_post = Comment(q[3])
            pending_payout = flagged_post['pending_payout_value']
        except Exception as e:
            print('Was unable to obtain pending payout value on https://steemit.com/'+str(q[3]))
            logging.exception(e)
            pending_payout = 0.000
        sql_list.append(q)
        flagged_post_dict = {'link': q[5], 'payout': pending_payout.amount or 0.000, 'category': q[2]}
        flagged_post_data.append(flagged_post_dict)
    flagged_post_data = sorted(flagged_post_data, key=lambda k: k['payout'],reverse=True)
    flagged_post_data = [dict(tupleized) for tupleized in set(tuple(item.items()) for item in flagged_post_data)]
    for fpd in flagged_post_data:
        if fpd['payout'] >0:
            table += '\n|{}|{}|{}|'.format(fpd['link'],str(fpd['payout'])+" SBD", fpd['category'])
    table += '\n --- \n'
    table1 = '|Link|Flagger|Category|\n|:-----------|:---------:|:--------|'
    for q in sql_list:
        table1 += '\n|{}|{}|{}|'.format(q[0], q[1], q[2])
    body = build_report_body(table)
    body += '\n\n\n{}'.format(table1)
    sql = cursor.execute(
    "SELECT sum(flag_rshares), sum(payout) FROM (SELECT flag_rshares, payout FROM steemflagrewards WHERE included == 0 AND " \
    "flagger IN flaggers)")
    q = sql.fetchone()
    removed = stm.rshares_to_sbd(float(q[0]))
    remain = q[1]
    body += "\n --- "
    try:
       body += get_rewards_chart(abs(removed),abs(remain))
    except Exception as e:
        print(e)    
    success_ratio = round((abs(removed)/(abs(remain)+abs(removed))*100),2)
    if(success_ratio >= 70):
        body +="# Mission Accomplished! \n"
        body +=" http://img200.imageshack.us/img200/3750/missionaccomplishedl.jpg "
    else:
        body +="# Mission Failed! \n"
        body +="https://static.giantbomb.com/uploads/original/0/329/1195180-psd3d036.jpg \n"
    body += "Reward removal at: "+str(success_ratio)+" % \n\n"
    body += flag_leaderboard()
    body += '\n\n\n <hr><div class="pull-left"><a href="https://discordapp.com/invite/fmE7Q9q"></a></div> If you feel you\'ve been wrongly flagged, check out @freezepeach, the flag abuse neutralizer. See the <a href="https://steemit.com/introduceyourself/@freezepeach/freezepeach-the-flag-abuse-neutralizer">intro post</a> for more details, or join the <a href="https://discordapp.com/invite/fmE7Q9q">discord server.</a><hr>'
    logging.info('Generated post body')
    benlist = []
    flags = []
    #queries flags exceeding minimum payout
    payoutflags = cursor.execute(
        'SELECT flagger FROM steemflagrewards WHERE included == 0 AND flagger IN flaggers')
    for q in payoutflags.fetchall():
        flags.append(str(q).split('\'')[1])#extracts username from tuple
    #queries flags below dust threshold
    dustflags = cursor.execute(
        'SELECT flagger FROM steemflagrewards WHERE (included == 0 AND dust == 1) AND flagger IN flaggers')
    for q in dustflags.fetchall():
        flags.append(str(q).split('\'')[1])#extracts username from tuple
    flaggers = set(flags)
    for flagger in flaggers:
        benlist.append({'account': flagger, 'weight': int(flags.count(flagger)/len(flags)*9500)})
    benlist= sorted(benlist, key=lambda k: k['account'],reverse=False)
    rep = stm.post(
        'Steem Flag Rewards Report - 8 Flagger Post - {}'.format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M")),
        body, 'steemflagrewards', tags=['steemflagrewards', 'abuse', 'steem', 'flag','busy'], beneficiaries=benlist,
        parse_body=True, self_vote=False, community='busy', app='busy/2.5.6')
    cursor.execute('UPDATE steemflagrewards SET included = 1 WHERE flagger in flaggers;')
    db.commit()
    return construct_authorperm(rep['operations'][0][1])


def fill_embed(embed: discord.Embed, names: list, template: str):
    """
    Function to add the contents of a list to a discord embed keeping the message size limit in mind
    """
    value = ''
    for n in names:
        if len(value + template.format(n[0])) < 1024:
            value += template.format(n[0])
        else:
            embed.add_field(name='...', value=value, inline=False)
            value = template.format(n[0])
    embed.add_field(name='...', value=value, inline=False)


async def queue_voting(ctx, sfr):
    """
    Voting on steemflagrewards mentions one after one once the voting power of the account reached 90%. This maintains a rather stable flagging ROI
    """
    global queueing
    while queueing:
        while sfr.vp < cfg.MIN_VP:  # For not failing because of unexpected manual votes
            await asyncio.sleep(sfr.get_recharge_timedelta(cfg.MIN_VP).total_seconds())
            sfr.refresh()
        next_queued = cursor.execute(
            'SELECT comment, flagger, category, weight, followon FROM steemflagrewards WHERE queue == 1 ORDER BY created ASC LIMIT 1;').fetchone()
        if not next_queued:
            queueing = False
            await ctx.send('No more mentions left in the queue. Going back to instant voting mode.')
            return
        authorperm, flagger, cats, weight, follow_on = next_queued
        comment = Comment(authorperm, steem_instance=stm)
        comment_age = comment.time_elapsed()
        if comment_age < datetime.timedelta(minutes=15):
            sleeptime = (datetime.timedelta(minutes=15) - comment_age).total_seconds()
            await ctx.send('Comment is younger than 15 mins - sleeping for %.1f mins.' % (sleeptime/60))
            logging.info('Comment is younger than 15 mins - sleeping for %.1f mins.' % (sleeptime/60))
            await asyncio.sleep(sleeptime)
        try:
            if not sfr.get_vote(comment):
                comment.upvote(weight, sfr.name)
                await asyncio.sleep(cfg.STEEM_MIN_VOTE_INTERVAL)  # sleeps to account for STEEM_MIN_VOTE_INTERVAL
            else:
                await ctx.send('Already voted on this!')
                cursor.execute('UPDATE steemflagrewards SET queue = 0 WHERE comment == ?', (authorperm,))
                db.commit()
                sfr.refresh()
                return
        except VotingInvalidOnArchivedPost:
            await ctx.send(
                'Sadly one comment had to be skipped because it got too old.'
                'Maybe the author can delete the comment and write a new one?')
            cursor.execute('UPDATE steemflagrewards SET queue = 0 WHERE comment == ?', (authorperm,))
            db.commit()
            continue
        except Exception as e:
            await ctx.send(f'Something went wrong while upvoting {comment.author}\'s comment. Skipping it.')
            logging.exception(e)
            cursor.execute('UPDATE steemflagrewards SET queue = 0 WHERE comment == ?', (authorperm,))
            db.commit()
            continue
        await ctx.send(f'Sucessfully voted on mention by {flagger} out of the queue.')
        if not follow_on:
            await asyncio.sleep(get_wait_time(sfr))
            body = get_approval_comment_body(flagger, cats)
            stm.post('', body, reply_identifier=authorperm,
                     community='SFR', parse_body=True,
                     author=sfr.name)
            await ctx.send('Commented on queued mention.')
        cursor.execute('UPDATE steemflagrewards SET queue = 0 WHERE comment == ?', (authorperm,))
        db.commit()
        sfr.refresh()
    return

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
bot = Bot(description='SteemFlagRewards Bot', command_prefix='?')


@bot.command()
async def approve(ctx, link):
    """Checks post body for @steemflagrewards mention and https://steemit.com/ and must be in the flag_comment_review
    channel id """
    global queueing
    dust = False
    #obtains mods steem account based on pairing in config file and splits our username from single quotes
    approving_mod_steem_acct = 'steemflagrewards'
    for item in cfg.Moderators:
        if item['DiscordID'] == ctx.author.id:
            approving_mod_steem_acct = item['SteemUserName']
    await ctx.send("Approving mod's Steem Account identified as "+approving_mod_steem_acct+"!")
    print(approving_mod_steem_acct)
    if ctx.message.channel.id != cfg.FLAG_APPROVAL_CHANNEL_ID:
        await ctx.send('Send commands in the right channel please.')
        return
    logging.info('Registered command for {} by {}'.format(link, ctx.message.author.name))
    comment_perm = link.split('@')[-1]
    try:
        flaggers_comment = Comment(comment_perm, steem_instance=stm)
    except ContentDoesNotExistsException:
        await ctx.send('Please look at your link again. Could not find the linked comment.')
        return
    flagger = Account(flaggers_comment['author'])
    sfr = Account(cfg.SFRACCOUNT, steem_instance=stm)
    if '@{}'.format(cfg.SFRACCOUNT) not in flaggers_comment['body']:
        await ctx.send("Could not find a @%s mention. Please check "
                       "the comment." % (cfg.SFRACCOUNT))
        return
    cats = get_abuse_categories(flaggers_comment['body'])
    if len(cats) == 0:
        await ctx.send('No abuse category found.')
        return
    await ctx.send('Abuse category acknowledged as {}'.format(', '.join(cats)))
    parent_perm = construct_authorperm(flaggers_comment['parent_author'],
                                       flaggers_comment['parent_permlink'])
    flagged_post = Comment(parent_perm, steem_instance=stm)
    cursor.execute('SELECT * FROM steemflagrewards WHERE comment == ?', (flagged_post.authorperm,))
    if flagged_post['author'] == cfg.SFRACCOUNT:  # Check if flag is a follow on flag
        for i in range(2):
            parent_perm = construct_authorperm(flagged_post['parent_author'],
                                               flagged_post['parent_permlink'])
            flagged_post = Comment(parent_perm, steem_instance=stm)
        follow_on = True
        await ctx.send('Follow on flag spotted')
    elif cursor.fetchone():
        follow_on = True
        while True:
            parent_perm = construct_authorperm(flagged_post['parent_author'],
                                               flagged_post['parent_permlink'])
            flagged_post = Comment(parent_perm, steem_instance=stm)
            if cursor.execute('SELECT post FROM steemflagrewards WHERE post == ?',
                              (flagged_post.authorperm,)).fetchall():
                break
    else:
        follow_on = False
        cursor.execute('SELECT post FROM steemflagrewards WHERE post == ?', (flagged_post.authorperm,))
        if cursor.fetchall():
            await ctx.send(
                'There has already been some flagging happenin\' on that post/comment. Please consider using the follow on flag feature if you don\'t make a good comment.')
            follow_on = True
    logging.info(f'Flagged post: {flagged_post.authorperm}')
    weight = 0
    for v in flagged_post['active_votes']:
        if int(v['rshares']) < 0 and v['voter'] == flagger['name']:
            await ctx.send('Downvote confirmed')
            sfrdvote = v

            if stm.rshares_to_sbd(abs(int(v['rshares']))) < 0.0195: #SFR current minimum flag threshold for upvotes
                dust = True
            follow_on_ROI = 0.1
            new_flag_ROI = 0.2
            first_flag_ROI = 0.25
            ROI = 1.05

            if follow_on is True:
                ROI += follow_on_ROI
            elif follow_on is False:
                ROI += new_flag_ROI
            else:
                await ctx.send('Something went very wrong. I\'m sorry about the inconvenience.')
            if not cursor.execute('SELECT flagger FROM steemflagrewards WHERE flagger == ?;', (flagger.name,)):
                ROI += first_flag_ROI

            if queueing:
                voting_power = cfg.MIN_VP * 100
            else:
                voting_power = sfr.vp * 100
            vote_pct = stm.rshares_to_vote_pct(int(abs(int(v['rshares'])) * ROI),  # ROI for the flaggers
                                               steem_power=sfr.sp,
                                               voting_power=voting_power)
            min_vote_pct = stm.rshares_to_vote_pct(0.0245 / stm.get_sbd_per_rshares(),
                                                   steem_power=sfr.sp,
                                                   voting_power=voting_power)
            weight = max(round((vote_pct / 10000) * 100), round((min_vote_pct / 10000) * 100))
    if dust is not True:
        if sfr.get_vote(flaggers_comment):
            await ctx.send('Already voted on this!')
            return
        elif not weight:
            await ctx.send('Apparently, the post wasn\'t flagged!')
            return
        if not queueing or queue_bypass == True:
            logging.info('Attempting to vote now.')
            comment_age = flaggers_comment.time_elapsed()
            if comment_age < datetime.timedelta(minutes=15):
                sleeptime = (datetime.timedelta(minutes=15) - comment_age).total_seconds()
                await ctx.send('Comment is younger than 15 mins - sleeping for %.1f mins.' % (sleeptime/60))
                logging.info('Comment is younger than 15 mins - sleeping for %.1f mins.' % (sleeptime/60))
                await asyncio.sleep(sleeptime)
            flaggers_comment.upvote(weight=weight, voter=sfr.name)
            await ctx.send('Upvoted.')
            cursor.execute('INSERT INTO steemflagrewards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
                flagger.name, flaggers_comment.authorperm, flagged_post.authorperm, ', '.join(cats),
                flaggers_comment['created'], False,
                stm.rshares_to_sbd(sfrdvote['rshares']), False, weight, follow_on, dust, approving_mod_steem_acct, False))
            db.commit()
            if not follow_on:
                await asyncio.sleep(get_wait_time(sfr))
                body = get_approval_comment_body(flaggers_comment['author'], cats,dust)
                stm.post('', body,
                         reply_identifier=flaggers_comment['authorperm'],
                         community='SFR', parse_body=True,
                         author=sfr.name)
                await ctx.send('Commented.')
        else:
            await ctx.send('Queued upvote for later on.')
            cursor.execute('INSERT INTO steemflagrewards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
                flagger.name, flaggers_comment.authorperm, flagged_post.authorperm, ', '.join(cats),
                flaggers_comment['created'], False,
                stm.rshares_to_sbd(sfrdvote['rshares']), queueing, weight, follow_on, dust, approving_mod_steem_acct, False))
            db.commit()
        q = \
            cursor.execute(
                'SELECT COUNT(DISTINCT flagger) FROM steemflagrewards WHERE included == 0;').fetchone()[
                0]
        await ctx.send('Now at {} out of 9 needed flaggers for a report.'.format(q))
        if q > 8:
            await ctx.send('Hit flagger threshold. Checking last post age.')
            last_post_age = (Comment(construct_authorperm(sfr.get_blog_entries()[0]))).time_elapsed()
            if last_post_age < datetime.timedelta(hours=8):
                await ctx.send("Posted flagger report less than 8 hours ago so holding off on the report")
                return
            else:
                await ctx.send("Last flagger post has been over 8 hours ago so posting report.")
            r = report()
            msg = 'Sucessfully posted a new flagger report! Check it out! (And upvote it as well :P)\nhttps://steemit.com/{}'.format(
                r)
            await ctx.send(msg)
            postpromo = bot.get_channel(cfg.POST_PROMOTION_CHANNEL_ID)
            await postpromo.send(msg)
            sfr.claim_reward_balance()
        sfr.refresh()
        if sfr.vp < cfg.MIN_VP and not queueing:
            await ctx.send(
                'Hey my mojo is getting low. I should take a break...\nThat\'s why I\'ll go into queue mode now.'.format(
                    str(round(sfr.get_voting_value_SBD(), 3))))
            queueing = True
            await queue_voting(ctx, sfr)
    else:
        if not follow_on:
            await asyncio.sleep(get_wait_time(sfr))
            body = get_approval_comment_body(flaggers_comment['author'], cats,dust)
            stm.post('', body,
                     reply_identifier=flaggers_comment['authorperm'],
                     community='SFR', parse_body=True,
                     author=sfr.name)
            await ctx.send('Commented.')
        cursor.execute('INSERT INTO steemflagrewards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
            flagger.name, flaggers_comment.authorperm, flagged_post.authorperm, ', '.join(cats),
            flaggers_comment['created'], False,
            stm.rshares_to_sbd(sfrdvote['rshares']), False, weight, follow_on, dust, approving_mod_steem_acct, False))
        db.commit()
        q = \
            cursor.execute(
                'SELECT COUNT(DISTINCT flagger) FROM steemflagrewards WHERE included == 0;').fetchone()[
                0]
        await ctx.send('Now at {} out of 9 needed flaggers for a report.'.format(q))
        if q > 8:
            await ctx.send('Hit flagger threshold. Checking last post age.')
            last_post_age = (Comment(cfg.SFRACCOUNT+'/'+sfr.get_blog_entries()[0]['permlink'])).time_elapsed()
            if last_post_age < datetime.timedelta(hours=8):
                await ctx.send("Posted less than 8 hours ago so holding off on the report")
                return
            else:
                await ctx.send("Last post has been over 8 hours ago so posting report.")
            r = report()
            msg = 'Sucessfully posted a new report! Check it out! (And upvote it as well :P)\nhttps://steemit.com/{}'.format(
                r)
            await ctx.send(msg)
            postpromo = bot.get_channel(cfg.POST_PROMOTION_CHANNEL_ID)
            await postpromo.send(msg)
            sfr.claim_reward_balance()


@bot.command()
async def queue(ctx):
    queue = cursor.execute(
        'SELECT comment, post FROM steemflagrewards WHERE queue == 1 ORDER BY created ASC;').fetchall()
    if not queue:
        await ctx.send('No mention in the queue')
        return
    sfr = Account(cfg.SFRACCOUNT, steem_instance=stm)
    queue_embed = discord.Embed(title='@steemflagrewards voting queue',
                                description=f'Next vote will happen in {sfr.get_recharge_timedelta(cfg.MIN_VP) // 60}.',
                                color=discord.Color.red())
    for mention in queue:
        queue_embed.add_field(name=f'Number {queue.index(mention) + 1} in the queue',
                              value=f'[{mention[0]}](https://steemit.com/{mention[1]}/#{mention[0]})')
    await ctx.send(embed=queue_embed)


@bot.command()
async def clear_queue(ctx):
    """
    Clears entire voting queue
    """
    cursor.execute('UPDATE steemflagrewards SET queue = 0 WHERE queue == 1')
    db.commit()
    await ctx.send('Queue has been successfully cleared!')
    return

@bot.command()
async def unqueue(ctx,permlink):
    """
    Removes post from queue by given permlink.
    """
    cursor.execute('UPDATE steemflagrewards SET queue = 0 WHERE comment == ?',('@'+permlink,))
    db.commit()
    await ctx.send('@'+permlink+' successfully removed from queue!')
    return

@bot.command()
async def queue_toggle(ctx):
    """
    Toggles bypass for queuing mechanism. If queue_bypass already set to TRUE, will set back to FALSE and vice versa.
    """
    global queue_bypass
    if queue_bypass == False:
        queue_bypass = True
        await ctx.send('Enabled queue override.')
    else:
        queue_bypass = False
        await ctx.send('Disabled queue override')
    return

@bot.command()
async def sdl(ctx, cmd: str, *mode: str):
    """
    Manage the list of the steemit defence league accounts with this command. Use it with ?sdl and one of the following
    """
    logging.info(f'{ctx.author.name} send sdl command with {cmd} ... {mode}')
    if cmd == 'add':
        if ctx.author.id not in cfg.SDL_LIST_EDITORS:
            await ctx.send('You do not have permissions to edit the SDL list.')
            return
        if not mode:
            await ctx.send('Please provide at least one account name.')
            return
        for i in mode:
            if '@' in i:
                i = i.split('@')[-1]
            try:
                acc = Account(i)
            except AccountDoesNotExistsException:
                await ctx.send(f'The account @{i} seems to not exist on the steem blockchain.')
                continue
            if cursor.execute('SELECT name FROM sdl WHERE name == ?', (acc.name,)).fetchall():
                await ctx.send(f'Account @{acc.name} already exists in the list.')
                continue
            if acc['received_vesting_shares'].amount > 0:
                delegation = True
            else:
                delegation = False
            cursor.execute('INSERT INTO sdl VALUES (?, ?, ?)', (acc.name, acc['created'], delegation,))
            await ctx.send(f'Added @{acc.name} to the list.')
        db.commit()
    elif cmd == 'remove':
        if ctx.author.id not in cfg.SDL_LIST_EDITORS:
            await ctx.send('You do not have permissions to edit the SDL list.')
            return
        if not mode:
            await ctx.send('Please provide at least one account name.')
            return
        for i in mode:
            if '@' in i:
                i = i.split('@')[-1]
            if not cursor.execute('SELECT name FROM sdl WHERE name == ?', (i,)).fetchall():
                await ctx.send(f'Could not find an account with the name @{i} in the list.')
                continue
            cursor.execute('DELETE FROM sdl WHERE name == ?', (i,))
            await ctx.send(f'Removed @{i} from the list.')
        db.commit()
    elif cmd == 'list':
        if 'steemd' in mode:
            link = '[{0}](https://steemd.com/@{0})\n'
        elif 'steemit' in mode:
            link = '[{0}](https://steemit.com/@{0})\n'
        else:
            msg = '\n**Accounts with delegations**\n```\n'
            names = cursor.execute('SELECT * FROM sdl ORDER BY delegation DESC, name ASC;').fetchall()
            for n in names:
                if n[2] == 0 and '**Accounts without delegations**' not in msg:
                    msg += '```\n**Accounts without delegations**\n```\n'
                msg += f'{n[0]}\n'
            await ctx.send(msg + '```')
            return
        delegated = discord.Embed(title='SDL with delegation',
                                  description='A list of Steemit Defence League accounts with a delegation (potentially by @steem)',
                                  color=discord.Color.gold())
        undelegated = discord.Embed(title='SDL without delegation',
                                    description='A list of Steemit Defence League accounts without delegations',
                                    color=discord.Color.blurple())
        names = cursor.execute('SELECT name FROM sdl WHERE delegation == 1 ORDER BY name ASC;').fetchall()
        fill_embed(delegated, names, link)
        names = cursor.execute('SELECT name FROM sdl WHERE delegation == 0 ORDER BY name ASC;').fetchall()
        fill_embed(undelegated, names, link)
        if 'delegated' in mode:
            await ctx.send(embed=delegated)
        elif 'undelegated' in mode:
            await ctx.send(embed=undelegated)
        else:
            await ctx.send(embed=delegated)
            await ctx.send(embed=undelegated)
    elif cmd == 'update':
        for i in cursor.execute('SELECT name FROM sdl WHERE delegation == 1;').fetchall():
            acc = Account(i[0])
            if acc['received_vesting_shares'] == 0:
                cursor.execute('UPDATE sdl SET delegation = 0 WHERE name == ?', i)
                await ctx.send(f'@{i[0]} got his delegation removed. :tada:')
                continue
            await ctx.send(f'@{i[0]} still got his delegation :(')
        db.commit()
    elif cmd == 'file':
        filename = '{}.steemitdefenseleague.txt'.format(datetime.datetime.now().strftime('%Y%m%d'))
        with open(filename, 'w+') as f:
            accounts = cursor.execute('SELECT name FROM sdl ORDER BY name ASC;').fetchall()
            for i in accounts:
                f.write(i[0] + '\n')
        await ctx.send(file=discord.File(filename))
    else:
        await ctx.send('Unknown command.')


@bot.command()
async def status(ctx):
    """Returns the current status of the SFR account."""
    logging.info('Registered status command')
    embed = discord.Embed(title='SFR Status', description='The current status of the SFR bot and account.',
                          color=discord.Color.blue())
    sfr = Account(cfg.SFRACCOUNT, steem_instance=stm)
    embed.add_field(name='Bot', value='Up and running', inline=False)
    flaggers, mentions = cursor.execute(
        "SELECT COUNT(DISTINCT flagger), COUNT(comment) FROM "
        "steemflagrewards WHERE included == 0;").fetchone()
    embed.add_field(name='Flaggers', value='{}/9'.format(flaggers), inline=False)
    embed.add_field(name='Mentions', value=mentions, inline=False)
    payout_removed, total_mentions = cursor.execute(
        "SELECT SUM(payout), COUNT(payout) FROM steemflagrewards WHERE "
        "created > DATETIME(\'now\', \'-7 days\');").fetchone()
    embed.add_field(name='Removed payouts in the last 7 days',
                    value=round(payout_removed or 0, 3), inline=False)
    embed.add_field(name='Total mentions approved in the last 7 days',
                    value=total_mentions)
    embed.add_field(name='Steem Power', value=round(sfr.get_steem_power(), 3), inline=False)
    embed.add_field(name='Voting Mana', value=round(sfr.vp, 2), inline=False)
    embed.add_field(name='VP --> 100%', value=sfr.get_recharge_time_str(100), inline=False)
    embed.add_field(name='Vote Value', value=round(sfr.get_voting_value_SBD(), 3), inline=False)
    embed.add_field(name='Reputation', value=round(sfr.get_reputation(), 3), inline=False)
    embed.add_field(name='Resource Credit %', value=round(sfr.get_rc_manabar()['current_pct'], 1), inline=False)
    post = sfr.get_blog(limit=1)[0]
    embed.add_field(name='Latest Post',
                    value='[{}](https://steemit.com/@{}/{})'.format(post['title'], post['author'], post['permlink']),
                    inline=False)
    embed.add_field(name='Awesomeness', value='Over 9000', inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def updatenodes(ctx):
    """Updates the nodes using the built in function that is based on hourly run benchmarks. Thanks holger80 for that feature."""
    global stm
    NodeList().update_nodes(steem_instance=stm)
    await ctx.send('Updated nodes using @fullnodeupdate.')

@bot.command()
async def update_general(ctx):
    """
    Updates description of general channel with SFR info
    """
    chan = bot.get_channel(398612955270217730)
    sfr = Account(cfg.SFRACCOUNT, steem_instance=stm)
    SP = sfr.get_steem_power()
    Vote_Value = sfr.get_voting_value_SBD()
    payout_removed, total_mentions = cursor.execute(
        "SELECT SUM(payout), COUNT(payout) FROM steemflagrewards WHERE "
        "created > DATETIME(\'now\', \'-7 days\');").fetchone()
    top = "7-day Stats | Payouts Removed: $"+str(round(payout_removed or str("Error"),2))+" | Total Mentions: "+str(total_mentions or str("Error"))+" | SFR Bot's Current SP: "+str(round(SP,0))+" | Upvote Value: "+str(round(Vote_Value,3))+" SBD"
    await chan.edit(topic=top)
    print(chan.topic)
    return

@bot.event
async def on_ready():
    global queueing
    sfr = Account(cfg.SFRACCOUNT, steem_instance=stm)
    queue_length = cursor.execute('SELECT count(*) FROM steemflagrewards WHERE queue == 1;').fetchone()
    if (sfr.vp < cfg.MIN_VP or queue_length[0] > 0) and queue_bypass == False:
        flag_comment_review = bot.get_channel(
            cfg.FLAG_APPROVAL_CHANNEL_ID)
        try:
            await flag_comment_review.send(
              f'Either the VP is below {cfg.MIN_VP} or there are unvoted queued mentions. Going into queue mode.')
        except:
            logging.exception('something went wrong sending a message to flag_comment_review')
        queueing = True
        await queue_voting(flag_comment_review, sfr)

def main():
    stm.wallet.unlock(os.getenv('PASSPHRASE'))
    bot.run(os.getenv('TOKEN'))

if __name__ == '__main__':
    main()
