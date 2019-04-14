import asyncio
import logging
import csv
import datetime
import discord
import os
import urllib.request
import sqlite3
import plotly.plotly as py
import plotly.graph_objs as go
import plotly
import emoji

from beem import Steem
from beem.account import Account
from beem.comment import Comment
from beem.exceptions import AccountDoesNotExistsException, ContentDoesNotExistsException, VotingInvalidOnArchivedPost
from beem.instance import set_shared_steem_instance
from beem.nodelist import NodeList
from beem.utils import construct_authorperm, addTzInfo
from collections import defaultdict
from datetime import timedelta
from discord.ext.commands import Bot
from decimal import Decimal
from privex.steemengine import SteemEngineToken

import sfr_config as cfg

class RangeDict(dict):
    def __getitem__(self, item):
        if type(item) != range:
            for key in self:
                if item in key:
                    return self[key]
        else:
            return super().__getitem__(item)

# http://www.clker.com/cliparts/A/Z/x/N/T/o/red-shield2.svg graphic used for mod ranks
                            
logging.basicConfig(level=logging.INFO, filename=cfg.LOGFILE)

db = sqlite3.connect(cfg.DATABASEFILE)
cursor = db.cursor()

nodes = NodeList().get_nodes()
#stm = Steem(node='https://anyx.io')
stm = Steem(node='https://rpc.usesteem.com') #hard coded due to plugin dependencies
set_shared_steem_instance(stm)
queueing = False
stm_eng = SteemEngineToken()

##################################################
# Uncomment for the initial setup of the database and plotly credential file using env variable
# cursor.execute('''CREATE TABLE steemflagrewards
# (flagger TEXT, comment TEXT, post TEXT, category TEXT, created TEXT, included BOOL, payout REAL, queue BOOL, weight REAL, followon BOOL, dust BOOL default '0', approved_by TEXT, mod_included BOOL, flag_rshares INTEGER, paid BOOL, resolved BOOL)''')
# cursor.execute('CREATE TABLE flaggers (name TEXT)')
# cursor.execute('CREATE TABLE sfr_posts (post TEXT, created TEXT)')
# cursor.execute('CREATE TABLE sdl (name TEXT, created TEXT, delegation BOOL)')
# db.commit()
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
            if cat == 'spam' and 'porn spam' in body:
                continue
            cats.append(cat)
    return cats


def get_approval_comment_body(flagger, abuse_categories, dust=False):
    """ assemble the body for the flag approval comment """
    cat_string = ''
    #for cat in abuse_categories:
    #    cat_string += cfg.CATEGORIES[cat]
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
    trace = go.Pie(labels=labels, values=values)
    try:
        charturl = py.plot([trace], filename='flagger_pie_chart_'+str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M")), auto_open=True)
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
           '[Discord]({})\n\n https://ipfs.busy.org/ipfs/' \
           'QmevTmxS7fQ6qggmaToEpeMbWxN1AF3xojGe3C1Qf9LBGt *Image compliments of @steemseph* \n \n' \
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
    return body

def build_report_body(flag_table):
    """ assemble the 8-flagges report post body """
    body = '## This post triggers once we have approved flags from 8 distinct ' \
           'flaggers via the SteemFlagRewards Abuse Fighting Community on our ' \
           '[Discord]({})\n\n https://ipfs.busy.org/ipfs/' \
           'QmPCPE97dB7HZjqWkmiKiSuuZUjy2AfUw64ZuLsVRLqvN4\n\n' \
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
    return body

def calculate_weight(vote):
	vote_pct = stm.rshares_to_vote_pct(int(abs(int(vote['rshares'])) * ROI),  # ROI for the flaggers
									   steem_power=sfr.sp,
									   voting_power=voting_power)
	min_vote_pct = stm.rshares_to_vote_pct(0.0245 / stm.get_sbd_per_rshares(),
										   steem_power=sfr.sp,
										   voting_power=voting_power)
	weight = max(round((vote_pct / 10000) * 100), round((min_vote_pct / 10000) * 100))

def check_db(flaggers_comment):
    cursor.execute('SELECT * FROM steemflagrewards WHERE comment == ?', (flaggers_comment.authorperm,))
    if cursor.fetchall():
        return True
    else:
        return False

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
                                'Rank': cfg.class_rank_dict[abs(q[1])],
                                'Image': cfg.class_img_dict[abs(q[1])]
                            })
    export_csv('sfr',rank_list)
    rank_list = sorted(rank_list, key=lambda k: k['rshares'],reverse=False)
    rank_markdown += '\n # SFR Leaderboard \n'
    rank_markdown += '|Flagger|SBD Amount|Rank|Image|\n|:-----------:|:---------:|:--------|:--------:|'
    for leader in rank_list:
        rank_markdown += '\n|{}|{}|{}|{}|'.format(leader['Downvoter'],str(leader['sbd_amount'])+" SBD", leader['Rank'], leader['Image'])
    return rank_markdown

def mod_leaderboard():
    cfg.mod_list = []
    rank_dict = {}
    rank_markdown = ''
    sql = cursor.execute("SELECT approved_by, count(approved_by) FROM steemflagrewards WHERE approved_by NOT IN ('None', 'steemflagrewards') GROUP BY approved_by ORDER BY count(approved_by) DESC")
    for q in sql.fetchall():
        cfg.mod_list.append({
                                'Mod': q[0],
                                'Total Approvals': q[1],
                                'Mod Rank': cfg.mod_rank_dict[abs(q[1])],
                                'Image': cfg.mod_img_dict[abs(q[1])]
                            })
    cfg.mod_list = sorted(cfg.mod_list, key=lambda k: k['Total Approvals'],reverse=True)
    rank_markdown += '\n # SFR Mod Leaderboard \n'
    rank_markdown += '|Mod|Total Approvals|Mod Rank|Image|\n|:-----------:|:---------:|:--------|:--------:|'
    for leader in cfg.mod_list:
        rank_markdown += '\n|{}|{}|{}|{}|'.format(leader['Mod'],str(leader['Total Approvals']), leader['Mod Rank'], leader['Image'])
    return rank_markdown

def export_csv(name,votelist):
    cwd = os.getcwd()
    filename=datetime.datetime.now().strftime(name+"%Y%m%d-%H%M%S.csv")
    keys = votelist[0].keys()
    outfile=open(cwd+'/'+filename,'w')
    writer=csv.DictWriter(outfile, keys)
    writer.writeheader()
    writer.writerows(votelist)

def insert_mention(approving_mod_steem_acct,cats,dust,flagger, flaggers_comment,flagged_post, sfrdvote, weight, queueing):
    included = False
    follow_on = False #column to be removed. follow on flag data will be archived
    paid = False
    resolved = False
    mod_included = False
    cursor.execute('INSERT INTO steemflagrewards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
        flagger.name, flaggers_comment.authorperm, flagged_post.authorperm, ', '.join(cats),
        flaggers_comment['created'], included,
        stm.rshares_to_sbd(sfrdvote['rshares']), queueing, weight, follow_on, dust, approving_mod_steem_acct, mod_included, int(sfrdvote['rshares']),paid, resolved))
    db.commit()

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
    for q in sql.fetchall():
        sql_list.append(q)
    sql_flaggable = cursor.execute( #Queries obtains flagged posts within the 5 day mark for report includsion and action
        "SELECT DISTINCT CASE WHEN category LIKE '%nsfw%' OR category LIKE '%porn spam%' THEN '[NSFW link](https://steemit.com/' || post || '#' || comment || ')' " \
        "ELSE '[Comment](https://steemit.com/\' || post || '#' || comment || ')' END, '@' || approved_by, category, post, comment, " \
        "CASE WHEN category LIKE '%nsfw%' OR category LIKE '%porn spam%' THEN '[NSFW link](https://steemit.com/' || post || ')' " \
        "ELSE '[Comment](https://steemit.com/\' || post || ')' END " \
        "FROM steemflagrewards WHERE created > DATETIME(\'now\', \'-5 days\') AND resolved == 0")
    table = 'Flaggable Posts \n |Link|Rewards Remaining|Category|\n|:----|:----------------:|:--------|'
    for q in sql_flaggable.fetchall():
        flagged_post_dict = {}
        try:
            flagged_comment = Comment(q[3])
            pending_payout = flagged_comment['pending_payout_value']
        except Exception as e:
            print('Was unable to obtain pending payout value on https://steemit.com/'+str(q[3]))
            logging.exception(e)
            pending_payout = "Null"
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
    sql_active = cursor.execute(
        "SELECT sum(flag_rshares), sum(payout) FROM steemflagrewards WHERE created > DATETIME(\'now\', \'-7 days\')")
    q = sql_active.fetchone()
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
    body += "Active SFR Flag Mention Reward removal at: "+str(success_ratio)+" % \n"
    body += mod_leaderboard()
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
    for q in sql.fetchall():
        sql_list.append(q)
    sql_flaggable = cursor.execute( #Queries obtains flagged posts within the 5 day mark for report includsion and action
        "SELECT DISTINCT CASE WHEN category LIKE '%nsfw%' OR category LIKE '%porn spam%' THEN '[NSFW link](https://steemit.com/' || post || '#' || comment || ')' " \
        "ELSE '[Comment](https://steemit.com/\' || post || '#' || comment || ')' END, '@' || flagger, category, post, comment, " \
        "CASE WHEN category LIKE '%nsfw%' OR category LIKE '%porn spam%' THEN '[NSFW link](https://steemit.com/' || post || ')' " \
        "ELSE '[Comment](https://steemit.com/\' || post || ')' END " \
        "FROM steemflagrewards WHERE created > DATETIME(\'now\', \'-5 days\') AND resolved == 0")
    db.commit()
    table = '### Flaggable Posts \n |Link|Rewards Remaining|Category|\n|:----|:------------|:--------|'
    for q in sql_flaggable.fetchall():
        flagged_post_dict = {}
        flag_list = []
        try:
            flagged_post = Comment(q[3])
            pending_payout = flagged_post['pending_payout_value']
        except Exception as e:
            print('Was unable to obtain pending payout value on https://steemit.com/'+str(q[3]))
            logging.exception(e)
            pending_payout = 0.000
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
        body +="\n # Mission Accomplished! \n"
        body +=" http://img200.imageshack.us/img200/3750/missionaccomplishedl.jpg "
    else:
        body +="\n # Mission Failed! \n"
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

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
bot = Bot(description='SteemFlagRewards Bot', command_prefix='?')


@bot.command()
async def approve(ctx, link):
    """Checks post body for @steemflagrewards mention and https://steemit.com/ and must be in the flag_comment_review
    channel id """
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
    logging.info(f'Flagged post: {flagged_post.authorperm}')
    weight = 0
    for v in flagged_post['active_votes']:
        if int(v['rshares']) < 0 and v['voter'] == flagger['name']:
            await ctx.send('Downvote confirmed')
            sfrdvote = v

            #if stm.rshares_to_sbd(abs(int(v['rshares']))) < cfg.dust_threshold: #SFR current minimum flag threshold for upvotes
            #    dust = True

            new_flag_ROI = cfg.new_flag_ROI
            first_flag_ROI = cfg.first_flag_ROI
            ROI = cfg.ROI

            ROI += new_flag_ROI
            if not cursor.execute('SELECT flagger FROM steemflagrewards WHERE flagger == ?;', (flagger.name,)): #check to see if it is flaggers first SFR flag
                ROI += first_flag_ROI

            voting_power = sfr.vp * 100
            weight = calculate_weight(v)
	if sfr.get_vote(flaggers_comment):
		await ctx.send('Already voted on this!')
		if check_db(flaggers_comment):
			return
		else:
			insert_mention(approving_mod_steem_acct,cats,dust,flagger, flaggers_comment,flagged_post, sfrdvote, weight, queueing)
			db.commit()
			return
	elif not weight:
		await ctx.send('Apparently, the post wasn\'t flagged!')
		return
	if not check_db(flaggers_comment):
		insert_mention(approving_mod_steem_acct,cats,dust,flagger, flaggers_comment,flagged_post, sfrdvote, weight, queueing)
		db.commit()
		await asyncio.sleep(get_wait_time(sfr))
		body = get_approval_comment_body(flaggers_comment['author'], cats,dust)
		stm.post('', body,
				 reply_identifier=flaggers_comment['authorperm'],
				 community='SFR', parse_body=True,
				 author=sfr.name)
		await ctx.send('Commented.')
	q = \
		cursor.execute(
			'SELECT COUNT(DISTINCT flagger) FROM steemflagrewards WHERE included == 0 AND created < DATETIME(\'now\', \'-7 days\') AND paid == 0;').fetchone()[
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

@bot.command()
async def beneficiary_heal(ctx,link):
    """Created beneficiary comment reply with given post identifier"""
    if ctx.message.channel.id != cfg.DEV_CHANNEL:
        await ctx.send('Send commands in the right channel please.')
        return
    comment = Comment(link)
    benedict = {}
    body = 'Greetings, '+'@'+comment['author']+'! This comment is part of the SteemFlagRewards Counterflag Healing program.' \
           ' You are set to receive 100% beneficiary rewards on this comment. If you would like to ' \
           'support this initiative, please consider a delegation to @neutralizer, @randohealer, or the @steemflagrewards main account. ' \
           'Thank you for flagging abuse! \n https://ipfs.busy.org/ipfs/QmP4xuT9vBQfswBJM74AUXbzP9vDJUHqrskYS85Gvqe28k \n ### Quick Delegation Links \n'
    for amount in [50, 100, 500, 1000]:
        body += " [{} SP](https://steemconnect.com/sign/" \
                "delegateVestingShares?delegator=&" \
                "delegatee={}&vesting_shares=" \
                "{}%20SP)".format(amount, 'neutralizer', amount)
    beneop = stm.post('',body, reply_identifier='@'+comment['author']+'/'+comment['permlink'],beneficiaries=[{'account': comment['author'], 'weight': 10000}],author='neutralizer')
    beneperm = construct_authorperm(beneop['operations'][0][1])
    benecomment = Comment(beneperm)
    benedict = {'identifier': benecomment.identifier,'created': benecomment['created']}
    return benedict

@bot.command()
async def blacklist_check(ctx,user):
    """Queries blacklist status of user using @themarkymark's Blacklist API."""
    contents = urllib.request.urlopen("http://blacklist.usesteem.com/user/"+user).read()
    bl = (str(contents).split('"blacklisted":[')[1]).split(']')[0]
    if bl == '':
        await ctx.send('@'+user+' is not on any blacklist tracked via the API')
        return
    else:
        blacklists = []
        bl = bl.split(',')
        for b in bl:
            blacklists.append(b.replace('"',''))
        await ctx.send('@'+user+' is on the following blacklists: ')
        for b in blacklists:
            await ctx.send(b)

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
async def post_mod_report(ctx):
    """
    Posts @sfr-mod-fund report
    """
    if ctx.message.channel.id != cfg.FLAG_APPROVAL_CHANNEL_ID:
        await ctx.send('Send commands in the right channel please.')
        return
    r = mod_report()
    msg = 'Sucessfully posted a new mod report! Check it out! (And upvote it as well :P)\nhttps://steemit.com/{}'.format(
        r)
    await ctx.send(msg)
    postpromo = bot.get_channel(cfg.POST_PROMOTION_CHANNEL_ID)
    await postpromo.send(msg)

@bot.command()
async def resolve(ctx,link):
    """
    Resolves a abuse post in the event the user corrects the issue.
    """
    comment_perm = link.split('@')[-1]
    cursor.execute('UPDATE steemflagrewards SET resolved = 1 WHERE post == ?',('@'+comment_perm,))
    db.commit()
    await ctx.send('Successfully resolved all mention records for @'+comment_perm+'!')
    return

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
    
@bot.command()
async def get_sfr_table_info(ctx):
    """
    Gets information about the sfr sql table
    """ 
    sql_info = []
    sql = cursor.execute('PRAGMA table_info(steemflagrewards)')
    for q in sql.fetchall():
        sql_info.append(q)
    await ctx.send(sql_info)

@bot.event
async def on_ready():
    sfr = Account(cfg.SFRACCOUNT, steem_instance=stm)


def main():
    stm.wallet.unlock(os.getenv('PASSPHRASE'))
    bot.run(os.getenv('TOKEN'))


if __name__ == '__main__':
    main()
