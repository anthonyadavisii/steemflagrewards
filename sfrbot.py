import asyncio
import datetime
import logging
import sqlite3
import os
import discord
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
# (flagger TEXT, comment TEXT, post TEXT, category TEXT, created TEXT, included BOOL, payout REAL, queue BOOL, weight REAL, followon BOOL, dust BOOL default '0', approved_by TEXT, mod_included BOOL)''')
# cursor.execute('CREATE TABLE flaggers (name TEXT)')
# cursor.execute('CREATE TABLE sdl (name TEXT, created TEXT, delegation BOOL)')
# db.commit()
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

def mod_report():
    """Posting a mod report post with the moderators set as beneficiaries."""
    sql_list = []
    sql = cursor.execute(
        "SELECT CASE WHEN category = 'nsfw' OR category = 'porn spam' THEN '[NSFW link](https://steemit.com/' || post || '#' || comment || ')' " \
        "ELSE '[Comment](https://steemit.com/' || post || '#' || comment || ')' END, '@' || approved_by, category, post, comment " \
        "FROM steemflagrewards WHERE mod_included == 0 AND approved_by IN (SELECT approved_by FROM steemflagrewards WHERE mod_included == 0 LIMIT 8)" \
        "LIMIT 50;")
    table = '|Link|Approved By|Category|\n|:-----------|:---------------:|:--------|'
    for q in sql.fetchall():
        sql_list.append(q)
        table += '\n|{}|{}|{}|'.format(q[0], q[1], q[2])
    body = build_mod_report_body(table)
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
    cursor.execute('DELETE FROM flaggers;')
    cursor.execute(
        'INSERT INTO flaggers SELECT DISTINCT flagger FROM steemflagrewards WHERE included == 0 ORDER BY created ASC LIMIT 8;')
    sql = cursor.execute(
        "SELECT CASE WHEN category = 'nsfw' OR category = 'porn spam' THEN '[NSFW link](https://steemit.com/' || post || '#' || comment || ')' " \
        "ELSE '[Comment](https://steemit.com/\' || post || '#' || comment || ')' END, '@' || flagger,'$' || ROUND(payout, 3), category, post " \
        "FROM steemflagrewards WHERE included == 0 AND flagger IN flaggers;")
    db.commit()
    table = '|Link|Flagger|Pending Payout|Category|\n|:----|:-------|:---------------:|:--------|'
    for q in sql.fetchall():
        try:
            flaggers_comment = Comment(q[4])
            pending_payout = flaggers_comment['pending_payout_value']
        except Exception as e:
            print('Was unable to obtain pending payout value on https://steemit.com/'+str(q[4]))
            logging.exception(e)
            pending_payout = "Null"
        table += '\n|{}|{}|{}|{}|'.format(q[0], q[1], pending_payout, q[3])
    body = build_report_body(table)
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

            if stm.rshares_to_sbd(abs(int(v['rshares']))) < 0.0245:
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
        if not queueing:
            logging.info('Attempting to vote now.')
            comment_age = flaggers_comment.time_elapsed()
            if comment_age < datetime.timedelta(minutes=15):
                sleeptime = (datetime.timedelta(minutes=15) - comment_age).total_seconds()
                logging.info('Comment is younger than 15 mins - sleeping for %.1f mins.' % (sleeptime/60))
                await asyncio.sleep(sleeptime)
            flaggers_comment.upvote(weight=weight, voter=sfr.name)
            await ctx.send('Upvoted.')
            if not follow_on:
                await asyncio.sleep(get_wait_time(sfr))
                body = get_approval_comment_body(flaggers_comment['author'], cats)
                stm.post('', body,
                         reply_identifier=flaggers_comment['authorperm'],
                         community='SFR', parse_body=True,
                         author=sfr.name)
                await ctx.send('Commented.')
        else:
            await ctx.send('Queued upvote for later on.')
        cursor.execute('INSERT INTO steemflagrewards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
            flagger.name, flaggers_comment.authorperm, flagged_post.authorperm, ', '.join(cats),
            flaggers_comment['created'], False,
            stm.rshares_to_sbd(sfrdvote['rshares']), queueing, weight, follow_on))
        db.commit()
        q = \
            cursor.execute(
                'SELECT COUNT(DISTINCT flagger) FROM steemflagrewards WHERE included == 0;').fetchone()[
                0]
        await ctx.send('Now at {} out of 9 needed flaggers for a report.'.format(q))
        if q > 8:
            await ctx.send('Hit flagger threshold. Posting report.')
            r = report()
            msg = 'Sucessfully posted a new report! Check it out! (And upvote it as well :P)\nhttps://steemit.com/{}'.format(
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
            body = get_approval_comment_body(flaggers_comment['author'], cats)
            stm.post('', body,
                     reply_identifier=flaggers_comment['authorperm'],
                     community='SFR', parse_body=True,
                     author=sfr.name)
            await ctx.send('Commented.')
        cursor.execute('INSERT INTO steemflagrewards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
            flagger.name, flaggers_comment.authorperm, flagged_post.authorperm, ', '.join(cats),
            flaggers_comment['created'], False,
            stm.rshares_to_sbd(sfrdvote['rshares']), False, weight, follow_on))
        db.commit()
        q = \
            cursor.execute(
                'SELECT COUNT(DISTINCT flagger) FROM steemflagrewards WHERE included == 0;').fetchone()[
                0]
        await ctx.send('Now at {} out of 9 needed flaggers for a report.'.format(q))
        if q > 8:
            await ctx.send('Hit flagger threshold. Posting report.')
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
    cursor.execute('UPDATE steemflagrewards SET queue = 0 WHERE queue == 1')
    db.commit()
    await ctx.send('Queue has been successfully cleared!')
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


@bot.event
async def on_ready():
    global queueing
    sfr = Account(cfg.SFRACCOUNT, steem_instance=stm)
    queue_length = cursor.execute('SELECT count(*) FROM steemflagrewards WHERE queue == 1;').fetchone()
    if sfr.vp < cfg.MIN_VP or queue_length[0] > 0:
        flag_comment_review = bot.get_channel(
            cfg.FLAG_APPROVAL_CHANNEL_ID)
        await flag_comment_review.send(
            f'Either the VP is below {cfg.MIN_VP} or there are unvoted queued mentions. Going into queue mode.')
        queueing = True
        await queue_voting(flag_comment_review, sfr)


def main():
    stm.wallet.unlock(os.getenv('PASSPHRASE'))
    bot.run(os.getenv('TOKEN'))


if __name__ == '__main__':
    main()
