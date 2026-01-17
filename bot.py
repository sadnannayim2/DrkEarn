import discord
from discord.ext import commands, tasks
import asyncio
import datetime
import sqlite3
import os
from dotenv import load_dotenv
import random

# Load environment variables
load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Database setup
def init_db():
    conn = sqlite3.connect('drkearn.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (discord_id TEXT PRIMARY KEY, 
                  money INTEGER DEFAULT 0,
                  last_ad_time TIMESTAMP,
                  ads_watched_today INTEGER DEFAULT 0,
                  total_ads_watched INTEGER DEFAULT 0)''')
    
    # Ads table (for tracking)
    c.execute('''CREATE TABLE IF NOT EXISTS ads
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT,
                  watch_time TIMESTAMP,
                  ad_type TEXT)''')
    
    conn.commit()
    conn.close()

# Initialize database
init_db()

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    reset_daily_ads.start()

@bot.event
async def on_member_join(member):
    """Auto-register users when they join"""
    conn = sqlite3.connect('drkearn.db')
    c = conn.cursor()
    
    # Check if user exists
    c.execute("SELECT discord_id FROM users WHERE discord_id = ?", (str(member.id),))
    if not c.fetchone():
        c.execute("INSERT INTO users (discord_id, money, ads_watched_today) VALUES (?, 0, 0)", 
                 (str(member.id),))
        conn.commit()
    
    conn.close()
    
    # Send welcome message
    embed = discord.Embed(
        title="🎉 Welcome to DrkEarn! 🎉",
        description="Earn money by watching ads on Discord!",
        color=discord.Color.green()
    )
    embed.add_field(name="Get Started", value="Type `!register` to start earning", inline=False)
    embed.add_field(name="Watch Ads", value="Type `!ads` to view available ads", inline=False)
    
    try:
        await member.send(embed=embed)
    except:
        pass  # Couldn't DM user

@bot.command(name='register')
async def register(ctx):
    """Register user in the system"""
    user_id = str(ctx.author.id)
    
    conn = sqlite3.connect('drkearn.db')
    c = conn.cursor()
    
    # Check if already registered
    c.execute("SELECT discord_id FROM users WHERE discord_id = ?", (user_id,))
    if c.fetchone():
        await ctx.send("✅ You are already registered!")
    else:
        c.execute("INSERT INTO users (discord_id, money, ads_watched_today) VALUES (?, 0, 0)", 
                 (user_id,))
        conn.commit()
        
        embed = discord.Embed(
            title="✅ Registration Successful!",
            description=f"Welcome {ctx.author.name}!",
            color=discord.Color.green()
        )
        embed.add_field(name="Your Discord ID", value=user_id, inline=False)
        embed.add_field(name="Starting Balance", value="💰 0", inline=False)
        embed.add_field(name="Next Step", value="Type `!ads` to start watching ads and earn money!", inline=False)
        
        await ctx.send(embed=embed)
    
    conn.close()

@bot.command(name='ads')
async def show_ads(ctx):
    """Show available ads to watch"""
    user_id = str(ctx.author.id)
    
    conn = sqlite3.connect('drkearn.db')
    c = conn.cursor()
    
    # Get user data
    c.execute("SELECT last_ad_time, ads_watched_today FROM users WHERE discord_id = ?", (user_id,))
    user_data = c.fetchone()
    
    if not user_data:
        await ctx.send("❌ Please register first using `!register`")
        conn.close()
        return
    
    last_ad_time, ads_watched = user_data
    
    # Check if user can watch ads
    can_watch = True
    cooldown_msg = ""
    
    if last_ad_time:
        last_time = datetime.datetime.fromisoformat(last_ad_time)
        time_diff = datetime.datetime.now() - last_time
        
        if time_diff.total_seconds() < 120:  # 2 minutes cooldown
            can_watch = False
            remaining = 120 - int(time_diff.total_seconds())
            cooldown_msg = f"\n⏰ Cooldown: {remaining} seconds remaining"
    
    # Create embed
    embed = discord.Embed(
        title="📺 Available Ads",
        description="Watch ads to earn money!",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Ads Watched Today", value=f"📊 {ads_watched}/10", inline=True)
    embed.add_field(name="Earnings per Ad", value="💰 100 Coins", inline=True)
    embed.add_field(name="Total Value", value="🪙 1,000 Coins for 10 ads", inline=True)
    
    if ads_watched >= 10:
        embed.add_field(name="Status", value="❌ Daily limit reached!\nCome back tomorrow.", inline=False)
    elif not can_watch:
        embed.add_field(name="Status", value=f"⏰ Please wait for cooldown{cooldown_msg}", inline=False)
    else:
        embed.add_field(name="Status", value="✅ Ready to watch ads!", inline=False)
    
    # Create buttons for ads
    if can_watch and ads_watched < 10:
        view = discord.ui.View()
        
        # Create 10 ad buttons (but we'll show max based on remaining)
        remaining_ads = 10 - ads_watched
        for i in range(min(3, remaining_ads)):  # Show up to 3 buttons at once
            ad_number = ads_watched + i + 1
            button = discord.ui.Button(
                label=f"Watch Ad {ad_number}",
                style=discord.ButtonStyle.green,
                custom_id=f"ad_{ad_number}"
            )
            button.callback = create_ad_callback(ad_number, ctx.author.id)
            view.add_item(button)
        
        embed.add_field(name="Action", value="Click a button below to watch an ad:", inline=False)
        await ctx.send(embed=embed, view=view)
    else:
        await ctx.send(embed=embed)
    
    conn.close()

def create_ad_callback(ad_num, user_id):
    """Create callback function for ad button"""
    async def ad_callback(interaction):
        if interaction.user.id != user_id:
            await interaction.response.send_message("❌ This button is not for you!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Generate random ad URL
        ad_urls = [
            "https://example-ad-network.com/ad1",
            "https://ads-provider.com/watch/video123",
            "https://promotional-content.net/offer456"
        ]
        
        ad_url = random.choice(ad_urls)
        
        # Create ad watching embed
        embed = discord.Embed(
            title=f"📺 Watching Ad {ad_num}",
            description=f"Please visit the link below and watch the ad for 30 seconds:",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Ad Link", value=f"[Click Here]({ad_url})", inline=False)
        embed.add_field(name="Instructions", value="1. Click the link\n2. Watch the ad completely\n3. Return here and click Verify", inline=False)
        
        # Create verify button
        view = discord.ui.View()
        verify_button = discord.ui.Button(
            label="✅ I Watched the Ad",
            style=discord.ButtonStyle.blurple,
            custom_id=f"verify_{ad_num}_{user_id}"
        )
        
        async def verify_callback(verify_interaction):
            if verify_interaction.user.id != user_id:
                await verify_interaction.response.send_message("❌ This is not for you!", ephemeral=True)
                return
            
            # Update database
            conn = sqlite3.connect('drkearn.db')
            c = conn.cursor()
            
            # Update user money and ad count
            c.execute('''UPDATE users 
                        SET money = money + 100, 
                            last_ad_time = ?,
                            ads_watched_today = ads_watched_today + 1,
                            total_ads_watched = total_ads_watched + 1
                        WHERE discord_id = ?''',
                     (datetime.datetime.now().isoformat(), str(user_id)))
            
            # Log the ad watch
            c.execute("INSERT INTO ads (user_id, watch_time, ad_type) VALUES (?, ?, ?)",
                     (str(user_id), datetime.datetime.now().isoformat(), f"ad_{ad_num}"))
            
            conn.commit()
            
            # Get updated balance
            c.execute("SELECT money FROM users WHERE discord_id = ?", (str(user_id),))
            new_balance = c.fetchone()[0]
            
            conn.close()
            
            # Success embed
            success_embed = discord.Embed(
                title="✅ Ad Watched Successfully!",
                description="You've earned 100 coins!",
                color=discord.Color.green()
            )
            success_embed.add_field(name="Earned", value="💰 +100 Coins", inline=True)
            success_embed.add_field(name="New Balance", value=f"🪙 {new_balance} Coins", inline=True)
            success_embed.add_field(name="Next Ad", value="⏰ Available in 2 minutes", inline=False)
            
            await verify_interaction.response.send_message(embed=success_embed)
            
            # Disable the button
            for item in view.children:
                item.disabled = True
            await interaction.edit_original_response(view=view)
        
        verify_button.callback = verify_callback
        view.add_item(verify_button)
        
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    return ad_callback

@bot.command(name='balance')
async def check_balance(ctx):
    """Check user's balance"""
    user_id = str(ctx.author.id)
    
    conn = sqlite3.connect('drkearn.db')
    c = conn.cursor()
    
    c.execute("SELECT money, total_ads_watched FROM users WHERE discord_id = ?", (user_id,))
    result = c.fetchone()
    
    if not result:
        await ctx.send("❌ Please register first using `!register`")
    else:
        money, total_ads = result
        
        embed = discord.Embed(
            title="💰 Your Balance",
            description=f"Earnings for {ctx.author.name}",
            color=discord.Color.gold()
        )
        embed.add_field(name="Current Balance", value=f"🪙 {money} Coins", inline=True)
        embed.add_field(name="Total Ads Watched", value=f"📊 {total_ads} ads", inline=True)
        embed.add_field(name="Total Value", value=f"💵 ₹{money / 10:.2f}", inline=True)
        
        await ctx.send(embed=embed)
    
    conn.close()

@bot.command(name='withdraw')
async def withdraw(ctx):
    """Withdraw money (example command)"""
    user_id = str(ctx.author.id)
    
    conn = sqlite3.connect('drkearn.db')
    c = conn.cursor()
    
    c.execute("SELECT money FROM users WHERE discord_id = ?", (user_id,))
    result = c.fetchone()
    
    if not result:
        await ctx.send("❌ Please register first using `!register`")
    elif result[0] < 1000:
        await ctx.send(f"❌ Minimum withdrawal is 1000 coins. You have {result[0]} coins.")
    else:
        # In a real app, you would process payment here
        embed = discord.Embed(
            title="🔄 Withdrawal Request",
            description="Withdrawal functionality example",
            color=discord.Color.orange()
        )
        embed.add_field(name="Requested Amount", value=f"🪙 {result[0]} Coins", inline=True)
        embed.add_field(name="Cash Value", value=f"💵 ₹{result[0] / 10:.2f}", inline=True)
        embed.add_field(name="Note", value="This is a demo. Real implementation would connect to payment gateway.", inline=False)
        
        await ctx.send(embed=embed)
    
    conn.close()

@bot.command(name='stats')
@commands.has_permissions(administrator=True)
async def bot_stats(ctx):
    """Admin command to see bot statistics"""
    conn = sqlite3.connect('drkearn.db')
    c = conn.cursor()
    
    # Get total users
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    # Get total money in system
    c.execute("SELECT SUM(money) FROM users")
    total_money = c.fetchone()[0] or 0
    
    # Get total ads watched
    c.execute("SELECT COUNT(*) FROM ads")
    total_ads = c.fetchone()[0]
    
    conn.close()
    
    embed = discord.Embed(
        title="📊 Bot Statistics",
        description="DrkEarn System Overview",
        color=discord.Color.purple(),
        timestamp=datetime.datetime.now()
    )
    
    embed.add_field(name="Total Users", value=f"👥 {total_users}", inline=True)
    embed.add_field(name="Total Money Distributed", value=f"🪙 {total_money} Coins", inline=True)
    embed.add_field(name="Total Ads Watched", value=f"📺 {total_ads}", inline=True)
    embed.add_field(name="Server Count", value=f"🌐 {len(bot.guilds)}", inline=True)
    
    await ctx.send(embed=embed)

@tasks.loop(hours=24)
async def reset_daily_ads():
    """Reset daily ad count for all users"""
    conn = sqlite3.connect('drkearn.db')
    c = conn.cursor()
    
    c.execute("UPDATE users SET ads_watched_today = 0")
    conn.commit()
    conn.close()
    
    print("Daily ads reset completed")

# Run the bot
if __name__ == "__main__":
    bot_token = os.getenv('DISCORD_BOT_TOKEN')
    if not bot_token:
        print("Error: DISCORD_BOT_TOKEN not found in environment variables")
    else:
        bot.run(bot_token)
