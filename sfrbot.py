import asyncio
import discord
import io
import os
import os.path
import pytablereader as ptr
import pytablewriter as ptw
import csv
import datetime
import collections
from steem import Steem
from steem.blockchain import Blockchain
from steem.steemd import Steemd
from steem.post import Post
from steem.account import Account
from steem.amount import Amount
from steem.instance import set_shared_steemd_instance
from beem.instance import set_shared_steem_instance as sssi
from beem.comment import Comment
from steem.converter import Converter
from beem import Steem as beem_Steem
from beem.account import Account as beem_account
from beem.amount import Amount as beem_amount
from discord.ext import commands
from discord.ext.commands import Bot
from collections import OrderedDict


#list for approved flag mention comments
approved = []

#list of authors whose comments have been approved since last report
approved_authors = []

#Variable used to carry 9th flagger data over for next report
carryover_approvals = []

#abuse categories
abusecats=['testing for rewards','comment spam', 'plagiarism', 'spam', 'copy/paste', 'identity theft', 'vote abuse','bid bot misuse', 'bid bot abuse', 'manipulation', 'collusive voting', 'failure to tag nsfw', 'death threats','threat', 'vote farming', 'post farming','tag misuse', 'tag abuse', 'phishing', 'comment self-vote violation','scam']

description = '''sfrBot in Python'''
bot = Bot(description="SteemFlagRewards Bot", command_prefix='?', pm_help = True)

beem_nodes= [
	"wss://rpc.buildteam.io",
	 "wss://gtg.steem.house:8090", 
	 "wss://steemd.privex.io", 
	 "https://api.steemit.com/", 
	 "wss://rpc.steemliberator.com", 
	 "https://api.steem.house/"
 ]
my_nodes = [
		'https://rpc.buildteam.io/',
	'https://gtg.steem.house:8090/',
	'https://api.steemit.com/',
	'https://steemd.steemit.com/',
	'https://rpc.steemliberator.com',
	'https://steemd.minnowsupportproject.org'
	'https://steemd.steemitstage.com/',
]
nodes = my_nodes

steem = Steem(my_nodes)
set_shared_steemd_instance(Steemd(nodes=my_nodes))
stm = beem_Steem(beem_nodes)
stm.set_default_nodes(beem_nodes)
sssi(stm)

# Last effort node recycler and general purpose functions

def switch_nodes():
	global stm
	global steem
	global nodes
	global beem_nodes
	nodes = node_recycler(nodes)
	steem = Steem(nodes)
	set_shared_steemd_instance(Steemd(nodes=nodes))
	stm = beem_Steem(beem_nodes)
	sssi(stm)
	steem.wallet.unlock()

def node_recycler(nodes):
	myorder = []
	node_count = len(nodes)
	myorder.append(2)
	i=3
	while i < node_count+1:
		myorder.append(i)
		i+=1
	myorder.append(1)
	nodes_new = [nodes[i-1] for i in myorder]
	return nodes_new

# Function to output to CSV file. Insert your own desired path

async def write_csv_row(action_dict):
	filename = datetime.datetime.now().strftime("sfr-log-"+"%m%d%Y.csv")
	if not os.path.isfile("/home/"+filename):
		with open("/home/"+filename,'a') as outfile:
			keys = action_dict.keys()
			writer=csv.DictWriter(outfile, keys)
			writer.writeheader()
			writer.writerow(action_dict)
	else:
		with open("/home/steem/"+filename,'a') as outfile:
			keys = action_dict.keys()
			writer=csv.DictWriter(outfile, keys)
			writer.writerow(action_dict)

# function to be removed once Beem transition complete / tested

async def get_payout_from_rshares(rshares):
	reward_fund = steem.get_reward_fund()
	reward_balance, recent_claims = reward_fund["reward_balance"], \
									reward_fund["recent_claims"]
	base_price = steem.get_current_median_history_price()["base"]
	fund_per_share = Amount(reward_balance).amount / float(recent_claims)
	payout = float(rshares) * fund_per_share * Amount(base_price).amount
	payout = round(payout,3)
	return payout

# builds markdown table given dict from approvals

def markdown_table_builder(sfrcommentlist):
	body = "| Link | Flagger | Payout | Category | Created |\n|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------|------------|--------------|-----------------|\n"
	for comment in sfrcommentlist:
		line = "| "+comment['Link']+" | "+comment['Flagger']+" | "+comment['$$$']+" | "+comment['Cat.']+" | "+str(comment['Created'])+" |\n"
		body = body+line
	return body

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')

@bot.command(pass_context = True)
async def approve_mention_link(ctx,link):
	"""Checks post pody for @steemflagrewards mention and https://steemit.com/ and must be in the flag_comment_review channel id"""
	global approved
	global approved_authors
	global abusecats
	global carryover_approvals
	print('0')
  # Brings 9th flagger and their approvals from previous round into current set and resets list
	if carryover_approvals:
		for approval in carryover_approvals:
			approved.append(approval)
		approved_authors.append(carryover_approvals[0]['Flagger'].replace('@',''))
		carryover_approvals = []
  #Ensures approvals occur in appropriate channel.
	if ctx.message.channel.id == '<insert your approval channel id>':
		sfrdvote = None
    #extracts post id from link
		id = "@"+(link.split('@'))[-1]
		p = Post(id,steem)
		c = Comment(id,steem_instance=stm)
		auth = beem_account(p.author)
		authsp = auth.get_steem_power()
    #acquires rewarding account
		a = beem_account('steemflagrewards',steem_instance=stm)
		a2 = Account('steemflagrewards',steem)
		sfrsp = a.get_steem_power()
		sfrratio = sfrsp / 10000
		print('1')
    # 
		if a.name.lower() in p.body.lower():
			for cat in abusecats:
				if cat.lower() in p.body.lower():
					await bot.say("Abuse category acknowledged as "+cat)
					v = p.active_votes
					parent_id="@"+p.parent_author+"/"+p.parent_permlink
					parentpost = Post(parent_id,steem)
          #gets parent post votes to check for downvotes
					pv = parentpost.active_votes
					vp = a.get_voting_power()
					weight = 5
					print('2')
					for vote in pv:
						if int(vote['rshares']) < 0 and vote['voter'] == p.author:
							await bot.say("Downvote Confirmed.")
              #saved downvote into variable for later use
							sfrdvote = vote
              # calculate vote percentage to match rshares of downvote
							vote_pct = stm.rshares_to_vote_pct(abs(int(vote['rshares'])), steem_power=sfrsp, voting_power=a2['voting_power'])
              #converts vote_pct to respective vote weight
							weight = round((vote_pct / 10000 )*100)
              # logic to cap if weight exceeds 100% and adjustable flag incentive.
							if weight >= 84:
								weight = 100
							else:
								#flag ROI incentive percent
								weight += 17
          #checks to make sure comment wasn't previously voted and an active post.
					if 'steemflagrewards' not in v and p.cashout_time != datetime.datetime(1969, 12, 31, 23, 59, 59):
						print("No SteemFlagRewards' votes detected. Post is active. Attempting voting.")
						try:
							c.upvote(weight,voter=a.name)
						except Exception as e:
							await bot.say("Error voting: "+str(e))
						else:
							await bot.say('Upvoted! Now commenting on mention comment!')
              #gets current time for later use
							n = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
              #generating comment body
							body= 'Steem Flag Rewards mention comment has been approved! Thank you for reporting this abuse, @'+p.author+' categorized as '+cat+'. This post was submitted via our Discord Community channel. Check us out on the following link!\n [SFR Discord](https://discord.gg/aXmdXRs)'
							#Posts approval comment
              try:
								stm.post('', body, a.name, permlink=None, reply_identifier=id, json_metadata=None, comment_options=None, community=None, tags=None, beneficiaries=None, self_vote=False)
							except Exception as e:
								print("Error Commenting: "+str(e))
							try:
                # gets approximate payout STU value in rshares
								payout = await get_payout_from_rshares(abs(int(sfrdvote['rshares'])))
								payout = "$"+str(payout)+" STU"
							except Exception as e:
								print("Error Getting Payout: "+str(e))
								payout = "Error"
              #generate approval dictionary
							action_dict = {'Link': '['+id+']('+link+')','Flagger': '@'+sfrdvote['voter'],'Cat.': cat,'$$$': payout, 'Created': p.created}
							# output approval to CSV
              await write_csv_row(action_dict)
							approved.append(action_dict)
							approved_authors.append(sfrdvote['voter'])
							approved_authors = list(set(approved_authors))
							await bot.say("Currently at "+str(len(approved_authors))+" of 9 approved flaggers until post")
							break
					else:
						await bot.say("Post has either paid out or been voted already.")
	if len(approved_authors) > 8:
		await bot.say('9th flagger notification. Posting Report...')
    #logic to remove approvals of 9th flagger to be carried over to next cycle / flagger post
		for approval in approved:
			if (approval['Flagger']).replace('@','') == approved_authors[1]:
				carryover_approvals.append(approval)
				approved.remove(approval)
		approved_authors.remove(approved_authors[1])
    #builds markdown table for post
		mdtable = markdown_table_builder(approved)
    #builds post body to include md table
		body = '## This post triggers once we have approved flags from 8 distinct flaggers via the SteemFlagRewards Abuse Fighting Community on our [Discord](https://discord.gg/NXG3JrH) \n\nhttps://steemitimages.com/DQmTJj2SXdXcYLh3gtsziSEUXH6WP43UG6Ltoq9EZyWjQeb/frpaccount.jpg\n\n Flaggers have been designated as post beneficiaries. Our goal is to empower abuse fighting plankton and minnows and promote a Steem that is less-friendly to abuse. It is simple. Building abuse fighters equals less abuse. \n\n\n'+mdtable
		benelist = []
    # generates list of beneficiaries current determined by quantity of flags instead of weight plus one to appropriate 1/<total qty of flags> reward percentage the rewarding account
		for author in approved_authors:
			authorcount = 0
			for approval in approved:
				if (approval['Flagger']).replace('@','') == author:
					authorcount +=1
			benelist.append({'account': author, 'weight': (round(10000 / (len(approved)+1)*authorcount))})
    #sorts benelist by account
		benelist = sorted(benelist, key=lambda k: k['account'])
		try:
			stm.post('Steem Flag Rewards Report - 8 Flagger Post -'+str(n),body, 'steemflagrewards', permlink=None, reply_identifier=None, json_metadata=None, comment_options=None, community=None, tags=['steemflagrewards','abuse','steem','steemit','flag'], beneficiaries=benelist, self_vote=False)
			approved_authors = []
			approved = []
		except Exception as e:
			print("Error posting:" +str(e))
		else:
			await bot.say("Report Published without Error")

#unlocks Steem wallet. Steem python functionality being deprecated
steem.wallet.unlock()

#unlocks Beem wallet w environmental variable
stm.wallet.unlock(os.getenv('PASSPHRASE'))
bot.run(os.getenv('TOKEN'))
