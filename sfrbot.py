import asyncio
import datetime
import logging
import sqlite3
import os

from beem import Steem
from beem.account import Account
from beem.comment import Comment
from beem.instance import set_shared_steem_instance
from beem.nodelist import NodeList
from dateutil.parser import parse
from discord.ext.commands import Bot

logging.basicConfig(level=logging.INFO)

db = sqlite3.connect('SFR.db')
cursor = db.cursor()

nodes = NodeList().get_nodes()
stm = Steem(node=nodes)
set_shared_steem_instance(stm)

categories = ['bid bot abuse',
              'bid bot misuse',
              'collusive voting',
              'comment self-vote violation',
              'comment spam',
              'copy/paste',
              'death threats',
              'failure to tag nsfw',
              'identity theft',
              'manipulation',
              'phishing',
              'plagiarism',
              'post farming',
              'scam',
              'spam',
              'tag abuse',
              'tag misuse',
              'testing for rewards',
              'threat',
              'vote abuse',
              'vote farming']  # Because the categories are sorted alphabetically, comment spam will be found before spam is, causing everything to work out as intended.


##################################################
# Uncomment for the initial setup of the database
# cursor.execute('''CREATE TABLE steemflagrewards
# (flagger TEXT, comment TEXT, post TEXT, category TEXT, created TEXT, included BOOL, payout REAL)''')
# cursor.execute('CREATE TABLE flaggers (name TEXT)')
# db.commit()
##################################################


def check_cat(comment):
    if '@steemflagrewards' in comment.lower():
        for cat in categories:
            if cat in comment.lower():
                return cat
        return None
    return None


def get_wait_time(account):
    for i in account.history_reverse(only_ops='comment'):
        if i['author'] == account['name']:
            wait = datetime.datetime.utcnow() - parse(i['timestamp'])
            wait = wait.seconds
            if wait > 20:  # TODO: Change to 3 once HF20 is out
                return 0
            else:
                return 20 - wait  # TODO: Change to 3 once HF20 is out as well


def report():
    cursor.execute('DELETE FROM flaggers;')
    cursor.execute(
        'INSERT INTO flaggers SELECT DISTINCT flagger FROM steemflagrewards WHERE included == 0 ORDER BY created ASC LIMIT 8;')
    sql = cursor.execute(
        'SELECT \'https://steemit.com/\' || post || \'#\' || comment, flagger, \'$\' || payout, category FROM steemflagrewards WHERE included == 0 AND flagger IN flaggers;')
    db.commit()
    table = '|Link|Flagger|Removed Rewards|Category|\n|:----|:-------|:---------------:|:--------|'
    count = 0
    for q in sql.fetchall():
        table += '\n|{}|{}|{}|{}|'.format(q[0], q[1], q[2], q[3])
        count += 1
    body = '## This post triggers once we have approved flags from 8 distinct flaggers via the SteemFlagRewards Abuse ' \
           'Fighting Community on our [Discord](https://discord.gg/NXG3JrH) ' \
           '\n\nhttps://steemitimages.com/DQmTJj2SXdXcYLh3gtsziSEUXH6WP43UG6Ltoq9EZyWjQeb/frpaccount.jpg\n\n Flaggers ' \
           'have been designated as post beneficiaries. Our goal is to empower abuse fighting plankton and minnows ' \
           'and promote a Steem that is less-friendly to abuse. It is simple. Building abuse fighters equals less ' \
           'abuse. \n\n\n{}'.format(table)
    logging.info('Generated post body')
    benlist = []
    sql = cursor.execute(
        'SELECT flagger, COUNT(*) FROM steemflagrewards WHERE flagger in flaggers GROUP BY flagger ORDER BY flagger;')
    for q in sql.fetchall():
        benlist.append({'account': q[0], 'weight': int(
            (q[1] / count) * 100 * 10)})  # Exchange 100 with the percentage you want @steemflagrewards to receive
    rep = stm.post(
        'Steem Flag Rewards Report - 8 Flagger Post - {}'.format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M")),
        body, 'steemflagrewards', tags=['steemflagrewards', 'abuse', 'steem', 'steemit', 'flag'], beneficiaries=benlist,
        parse_body=True, self_vote=False)
    cursor.execute('UPDATE steemflagrewards SET included = 1 WHERE flagger in flaggers;')
    db.commit()
    return '{}/{}'.format(rep['operations'][0][1]['author'], rep['operations'][0][1]['permlink'])


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
bot = Bot(description='SteemFlagRewards Bot', command_prefix='?', pm_help=True)


@bot.command()
async def updatenodes(ctx):
    """Updates the nodes using the built in function that is based on hourly run benchmarks. Thanks holger80 for that feature."""
    global nodes
    global stm
    nodes = NodeList().get_nodes()
    stm = Steem(node=nodes)
    await ctx.send('Updated nodes using @fullnodeupdate.')


@bot.command()
async def approve(ctx, link):
    """Checks post pody for @steemflagrewards mention and https://steemit.com/ and must be in the flag_comment_review
    channel id """
    global sfrdvote
    if ctx.message.channel.id != 419711548769042432:
        await ctx.send('Send commands in the right channel please.')
    else:
        logging.info('Registered command for {} by {}'.format(link, ctx.message.author.name))
        comment_perm = link.split('@')[-1]
        c = Comment(comment_perm)
        flagger = Account(c['author'])
        sfr = Account('steemflagrewards')
        sfrsp = stm.vests_to_sp(sfr['vesting_shares'].amount + sfr['received_vesting_shares'].amount - sfr[
            'delegated_vesting_shares'].amount)
        cat = check_cat(c['body'])
        if cat:
            await ctx.send('Abuse category acknowledged as {}'.format(cat))
            p = Comment('{}/{}'.format(c['parent_author'], c['parent_permlink']))
            for v in p['active_votes']:
                if int(v['rshares']) < 0 and v['voter'] == flagger['name']:
                    await ctx.send('Downvote confirmed')
                    sfrdvote = v
                    vote_pct = stm.rshares_to_vote_pct(abs(int(v['rshares'])), steem_power=sfrsp,
                                                       voting_power=sfr.get_voting_power())
                    weight = round((vote_pct / 10000) * 100)
                    if weight >= 83:
                        weight = 100
                    else:
                        weight += 17
            if sfr.get_vote(c):
                await ctx.send('Already voted on this!')
            else:
                logging.info('Attempting to vote now.')
                c.vote(weight=weight, account='steemflagrewards')
                body = 'Steem Flag Rewards mention comment has been approved! Thank you for reporting this abuse, @{} categorized as {}. This post was submitted via our Discord Community channel. Check us out on the following link!\n[SFR Discord](https://discord.gg/aXmdXRs)'.format(
                    c['author'], cat)
                asyncio.sleep(get_wait_time(sfr))
                stm.post('', body, reply_identifier='{}/{}'.format(c['author'], c['permlink']),
                         community='SFR', parse_body=True, author='steemflagrewards')
                await ctx.send('Upvoted and commented.')
                cursor.execute('INSERT INTO steemflagrewards VALUES (?, ?, ?, ?, ?, ?, ?)', (
                    flagger['name'], c.authorperm, p.authorperm, cat, c['created'], False,
                    round(stm.rshares_to_sbd(sfrdvote['rshares']), 3)))
                db.commit()
                q = \
                    cursor.execute(
                        'SELECT COUNT(DISTINCT flagger) FROM steemflagrewards WHERE included == 0;').fetchone()[
                        0]
                await ctx.send('Now at {} out of 9 needed flaggers for a report.'.format(q))
                if q > 8:
                    await ctx.send('Hit flagger threshold. Posting report.')
                    r = report()
                    await ctx.send('Sucessfully posted a new report! Check it out! (And upvote :P)\n'
                                   'https://steemit.com/@{}'.format(r))
                    postpromo = bot.get_channel(426612204717211648)
                    await postpromo.send('Sucessfully posted a new report! Check it out! (And upvote :P)\n'
                                   'https://steemit.com/@{}'.format(r))
        elif cat is None:
            await ctx.send('No abuse category found.')


if __name__ == '__main__':
    stm.wallet.unlock(os.getenv('PASSPHRASE'))

    bot.run(os.getenv('TOKEN'))
