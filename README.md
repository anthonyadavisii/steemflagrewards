# steemflagrewards
Steem Flag Rewards project code for Discord Bot used in incentivized flagging for increased moderation presence on the Steem blockchain.
This code is currently employed with the SteemFlagRewards Discord bot to reward users who properly identify abusive content falling within one of the defined categories. Most of these are derived from @steemcleaners list with a few notable additions to encompass various forms of voting abuse.

How can you run your own flag incentivization bot for your community? Although SteemFlagRewards is intent on branching out and we do currently have channels for various language support, we understand their are other moderation communities that may benefit from the flexibility of their own bot that may be customized.

Requirements
1. Discord Server with admin role and channel id for approvals.
2. Discord App for bot. (https://discordapp.com/developers/applications/me)
3. Python Scripting environment with dependent libraries installed.

With the above requirements met, you should be able to add the app to yoru Discord, run the bot code in python (make sure you input the passphrase) and test the ?approve command. I plan to create a more comprehensive guide in the future.

### TODO
- [ ] Only one steemflagrewards comment per main post/flagged comment to prevent spam
- [ ] `setup.py` and PyPi listing for easier usage
- [ ] Queuing up any votes if the VP of the @steemflagrewards account is low
