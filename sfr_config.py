#####################################################################
# General Settings
#####################################################################

class RangeDict(dict):
    def __getitem__(self, item):
        if type(item) != range:
            for key in self:
                if item in key:
                    return self[key]
        else:
            return super().__getitem__(item)

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

#ROI values
follow_on_ROI = 0.1
new_flag_ROI = 0.2
first_flag_ROI = 0.25
ROI = 1.15

#dust threshold
dust_threshold = 0.0195

# Mod Ranks

mod_rank_dict = RangeDict({range(1,9): 'M0 1-9 ',
                             range(10,99): 'M1 10-99 ', 
                             range(100,999): 'M2 100-999 ',
                             range(1000,4999): 'M3 1000-4999 ',
                             range(5000,9999): 'M4 5000-9999 ',
                             range(10000,14999): 'M5 10000-14999 ',
                             range(15000,19999): 'M6 15000-19999 ',
                             range(20000,24999): 'M7 20000-24999 ',
                             range(25000,29999): 'M8 25000-29999 ',
                             range(30000,34999): 'M9 30000-34999 ',
                             range(35000,39999): 'M10 35000-39999 ',
                             range(40000,49999): 'M11 40000-49999 ',
                             range(50000,999999999999999999): 'M12 50000 '}) 

mod_img_dict = RangeDict({range(1,9): 'https://i.imgur.com/YRCcsql.png',
                            range(10,99): 'https://i.imgur.com/ulEMxfP.png', 
                            range(100,999): 'https://i.imgur.com/tDIQq6G.png',
                            range(1000,4999): 'https://i.imgur.com/FrXncFr.png',
                            range(5000,9999): 'https://i.imgur.com/ORTwwBy.png',
                            range(10000,14999): 'https://i.imgur.com/b5mV01S.png',
                            range(15000,19999): 'FlagX6',
                            range(20000,24999): 'FlagX7',
                            range(25000,29999): 'FlagX8',
                            range(30000,34999): 'FlagX9',
                            range(35000,39999): 'FlagX10',
                            range(40000,49999): 'FlagX11',
                            range(50000,999999999999999999): 'FlagX12'}) 
						
# Flagger Ranks

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
                             range(1000000000000000,9999999999999999): 'F10 1 Quad',
                             range(10000000000000000,99999999999999999): 'F11 10 Quad',
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

# List of known abuse categories
# The keys are the keywords that need to be present in the flaggers
# comment in order to classify the flag category. The corresponding
# value is included in the reply of the SFR bot to the flagger's
# comment.
CATEGORIES = {
    'art paraphrasing': '\n* art paraphasing\nYou created a derivative artistic work but failed to cite the source(s) of inspiration. This is often a method employed to deceive curators in order to receive greater rewards.',
    'bid bot abuse': '\n* bid bot abuse\nYou bought votes to increase the rewards of your post above the value of its content.',
    'collusive voting': '\n* collusive voting\nThe votes on the content follows a repeated pattern suggestive of collusion between multiple users and /or alt accounts resulting in signficant overvaluation of content.',
    'comment self-vote violation': '\n* comment self-vote violation\nYou left a comment favorable about the post, you didn\'t upvote the post, and upvoted your own comment.',
	'contest spam': '\n* contest spam\nYou created a contest requiring votes, resteems or follows for entry. SFR considers these tactics manipulative. Posts that require upvotes to enter or play in a contest or game falls under spam or abuse in the [Steemit.com FAQ](https://steemit.com/faq.html).',
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

# Discord channel ID for testing and development
DEV_CHANNEL = 466237863227555860

#plotly config

plotlyuser= 'AnthonyADavisII'

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
WITNESSES = ['lukestokes.mhth', 'yabapmatt', 'themarkymark', 'cervantes', 'pjau', 'pfunk']

OTHERWITNESS = ['patrice', 'guiltyparties']

# List of supporting users to mention in the reports
SUPPORTERS = ['mids106','crokkon', 'freebornangel',
              'slobberchops', 'steevc', 'underground']

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
