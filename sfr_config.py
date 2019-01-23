#####################################################################
# General Settings
#####################################################################

# Location of the SFR logfile
LOGFILE = "logs/logs.txt"

# Filename of the SFR database file
DATABASEFILE = "SFR.db"


#####################################################################
# Core SteemFlagRewards settings
#####################################################################
# Name of the steemflagrewards Steem account
SFRACCOUNT = "steemflagrewards"

# Minimum VP % for votes
MIN_VP = 85

# List of known abuse categories
# The keys are the keywords that need to be present in the flaggers
# comment in order to classify the flag category. The corresponding
# value is included in the reply of the SFR bot to the flagger's
# comment.
CATEGORIES = {
    'bid bot abuse': '\n* bid bot abuse\nYou bought votes to increase the rewards of your post above the value of its content.',
    'collusive voting': '\n* collusive voting\nThe votes on the content follows a repeated pattern suggestive of collusion between multiple users and /or alt accounts resulting in signficant overvaluation of content.',
    'comment self-vote violation': '\n* comment self-vote violation\nYou left a comment favorable about the post, you didn\'t upvote the post, and upvoted your own comment.',
    'comment spam': '\n* comment spam\nYour comment has been repeated multiple times without regard to the post.',
    'copy/paste': '\n* copy/paste\nYour post mostly contains copied material from a source or stock content and is not your original work.',
    'failure to tag nsfw': '\n* failure to tag nsfw\nYour post should be tagged NSFW when it contains nudity, gore, extreme violence or anything inappropriate for general public viewing.',
    'identity theft': '\n* identity theft\nYou are pretending to be someone you are not.',
    'manipulation': '\ndescription placeholder',
    'phishing': '\n* phishing\nYou are trying to steal account keys, password or credentials.',
    'plagiarism': '\n* plagiarism\nYou are posting content that is not yours by copying it without sourcing or manipulating it to pass plagiarism tools.',
    'post farming': '\ndescription placeholder',
    'scam': '\n* scam\nThis post is a scam, designed to trick or defraud others.',
    'spam': '\n* spam\nYou are repetitively posting the same content or recyling contents after a period of time.',
    'tag abuse': '\n* tag abuse\nYou used tags irrelevant to your content or used the introduceyourself tag more than twice.',
    'tag misuse': '\ndescription placeholder',
    'testing for rewards': '\n* testing for rewards\nYou claimed to be “testing” but did not decline rewards.',
    'threat': '\ndescription placeholder',
    'vote abuse': '\ndescription placeholder',
    'porn spam': '\n* porn spam\nYou are spamming nsfw content. Often contains external image sources, affiliate links and failing to decline rewards on unoriginal content.',
    'nsfw': '\n* nsfw\nGeneric category for abuse that is nsfw in nature.',
    'vote farming': '\n* vote farming\nYou\'re churning out content (often low quality), in quick successions with abnormal number and/or upvote size.',
}


#####################################################################
# Discord settings
#####################################################################

# Discord channel ID for the announcements of new reports
POST_PROMOTION_CHANNEL_ID = 426612204717211648

# Discord channel ID for flag approvals
FLAG_APPROVAL_CHANNEL_ID = 419711548769042432

# list of Discord user IDs allowed to edit the SDL list
SDL_LIST_EDITORS = [
    405584423950614529,  # Iamstan
    272137261548568576,  # Leonis
    222012811172249600,  # Flugschwein
    398204160538836993,  # Naturicia
    347739387712372747,  # Anthonyadavisii
    102394130176446464,  # TheMarkyMark
    437647893072052233,  # Serylt
]

# Invite link to public SFR Discord
DISCORD_INVITE = "https://discord.gg/7pqKmg5"

# List of witnesses with significant delegations to mention in the reports
WITNESSES = ['lukestokes.mhth', 'yabapmatt', 'themarkymark', 'pjau', 'pfunk']

OTHERWITNESS = ['patrice', 'guiltyparties']

# List of supporting users to mention in the reports
SUPPORTERS = ['mids106', 'fulltimegeek', 'crokkon', 'freebornangel', 'lyndsaybowes',
              'slobberchops', 'steevc']

# List of moderators discord IDs paired to Steem username for mod incentives
Moderators = [
             {'DiscordID': 406099767823958016, 'SteemUserName': 'adamada'},
             {'DiscordID': 347739387712372747, 'SteemUserName': 'anthonyadavisii'},
             {'DiscordID': 222012811172249600, 'SteemUserName': 'flugschwein'},
             {'DiscordID': 405584423950614529, 'SteemUserName': 'iamstan'},
             {'DiscordID': 370011591539949568, 'SteemUserName': 'jplaughing'},
             {'DiscordID': 398204160538836993, 'SteemUserName': 'naturicia'},
             {'DiscordID': 244410741736734720, 'SteemUserName': 'serylt'},
             {'DiscordID': 272137261548568576, 'SteemUserName': 'enforcer48'},
             {'DiscordID': 400092684422873108, 'SteemUserName': 'steemseph'},
             {'DiscordID': 412077846626959360, 'SteemUserName': 'reazuliqbal'}
             ]

#####################################################################
# Steem-related settings
#####################################################################

# Steem minimum reply interval for comments in seconds
STEEM_MIN_REPLY_INTERVAL = 3

# Steem minimium vote interval in seconds
STEEM_MIN_VOTE_INTERVAL = 3
