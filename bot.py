#!/usr/bin/env python3
import os
import json
import asyncio
from time import time
import subprocess

from pySmartDL import SmartDL
from pydrive.auth import GoogleAuth
from mega import Mega

from upload import upload
from creds import Creds
from plugins import TEXT
from plugins.tok_rec import is_token
from plugins.dpbox import DPBOX
from plugins.wdl import wget_dl

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

gauth = GoogleAuth()
bot_token = Creds.TG_TOKEN

# Create the bot application
app = ApplicationBuilder().token(bot_token).build()

######################################################################################
# Async helper functions
######################################################################################

async def send_msg(update: Update, text: str):
    """Send message safely"""
    try:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        print("Send message error:", e)

######################################################################################
# Command Handlers
######################################################################################

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_msg(update, TEXT.START.format(update.message.from_user.first_name))

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_msg(update, TEXT.HELP)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_msg(update, TEXT.UPDATE)

async def auth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ID = str(update.message.from_user.id)
    try:
        gauth.LoadCredentialsFile(ID)
    except Exception as e:
        print("Cred file missing:", e)

    if gauth.credentials is None:
        authurl = gauth.GetAuthUrl()
        AUTH = TEXT.AUTH_URL.format(authurl)
        await send_msg(update, AUTH)
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()
        await send_msg(update, TEXT.ALREADY_AUTH)

async def token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    ID = str(update.message.from_user.id)

    if is_token(msg):
        token_val = msg.split()[-1]
        print(token_val)
        try:
            gauth.Auth(token_val)
            gauth.SaveCredentialsFile(ID)
            await send_msg(update, TEXT.AUTH_SUCC)
        except Exception as e:
            print("Auth Error:", e)
            await send_msg(update, TEXT.AUTH_ERROR)

async def revoke_tok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ID = str(update.message.chat_id)
    try:
        os.remove(ID)
        await send_msg(update, TEXT.REVOKE_TOK)
    except Exception as e:
        print(e)
        await send_msg(update, TEXT.REVOKE_FAIL)

######################################################################################
# Upload handler
######################################################################################

async def UPLOAD(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.split()[-1]
    sent_message = await update.message.reply_text(TEXT.PROCESSING)

    ID = str(update.message.chat_id)
    if not os.path.isfile(ID):
        await send_msg(update, TEXT.NOT_AUTH)
        return

    DownloadStatus = False

    try:
        if "openload" in url or "oload" in url:
            await sent_message.edit_text("Openload No longer available")
            return

        elif 'dropbox.com' in url:
            url = DPBOX(url)
            filename = url.split("/")[-1]
            print("Dropbox downloading started:", filename)
            await sent_message.edit_text(TEXT.DP_DOWNLOAD)
            filename = wget_dl(str(url))
            await sent_message.edit_text(TEXT.DOWN_COMPLETE)
            DownloadStatus = True

        elif 'mega.nz' in url:
            try:
                await sent_message.edit_text(TEXT.DOWN_MEGA)
                m = Mega.from_credentials(TEXT.MEGA_EMAIL, TEXT.MEGA_PASSWORD)
                filename = m.download_from_url(url)
                print("Mega download complete:", filename)
                await sent_message.edit_text(TEXT.DOWN_COMPLETE)
                DownloadStatus = True
            except Exception as e:
                print("Mega downloading error:", e)
                await sent_message.edit_text("Mega downloading error!!")

        else:
            try:
                filename = url.split("/")[-1]
                await sent_message.edit_text(TEXT.DOWNLOAD)
                filename = wget_dl(str(url))
                await sent_message.edit_text(TEXT.DOWN_COMPLETE)
                DownloadStatus = True
            except Exception as e:
                print(e)
                if TEXT.DOWN_TWO:
                    await sent_message.edit_text(
                        f"Downloader1 error: {e}\nDownloader2 starting..."
                    )
                    obj = SmartDL(url)
                    obj.start()
                    filename = obj.get_dest()
                    DownloadStatus = True
                else:
                    await sent_message.edit_text(f"Downloading error: {e}")
                    DownloadStatus = False

        if DownloadStatus:
            await sent_message.edit_text(TEXT.UPLOADING)
            SIZE = round(os.path.getsize(filename)/1048576)
            FILENAME = filename.split("/")[-1]
            try:
                FILELINK = upload(filename, update, context, TEXT.drive_folder_name)
            except Exception as e:
                print("Upload error:", e)
                await sent_message.edit_text(f"Uploading fail: {e}")
            else:
                await sent_message.edit_text(TEXT.DOWNLOAD_URL.format(FILENAME, SIZE, FILELINK))
            try:
                os.remove(filename)
            except:
                pass

    except Exception as e:
        print("UPLOAD handler error:", e)
        await sent_message.edit_text(f"Error: {e}")

######################################################################################
# Add handlers
######################################################################################

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CommandHandler("auth", auth))
app.add_handler(CommandHandler("revoke", revoke_tok))
app.add_handler(CommandHandler("update", status))
app.add_handler(MessageHandler(filters.Regex(r"http"), UPLOAD))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), token))

######################################################################################
# Run the bot
######################################################################################

if __name__ == "__main__":
    import asyncio
    asyncio.run(app.run_polling())
