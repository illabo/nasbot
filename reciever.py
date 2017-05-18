# -*- coding: utf-8 -*-

import os
import re
import time
import shelve
import thread
import base64
import bencode
import requests
import websocket

masters, token = eval(open("token.cfg", "r").read())
api_url = "https://api.telegram.org/bot%s/" % token
dl_dirs = {"Series":"/var/plex/series",
           "Movies":"/var/plex/movies",
           "General":"/home/nas/Downloads"}
pending_magnet = {}
gid_chat = {}
help_text = \
"""
This bot starts downloads by link or a .torrent file.
Sorts tv-shows, movies and general downloads apart automatically.
Accepts links and files from its master only.\n
*Commands:*
/special - specify download dir manually.
Usage: "/special download link, download dir"\n
More commands planned. ;)
"""


id_store = shelve.open("id_file", writeback=True)
if not len(id_store) == 2:
  id_store['gid_chat'], id_store['pending_magnet'] = \
  gid_chat, pending_magnet
else:
  gid_chat, pending_magnet = \
  id_store['gid_chat'], id_store['pending_magnet']
id_store.close()

def conductor(chat_id, method, params):
  request = ( '{"jsonrpc":"2.0",'\
              '"id":"%s",'\
              '"method":"%s",'\
              '"params":%s}'
            ) % (chat_id, method, params)
  wsocket.send(request)
  with open("nasbot_ws.log", "a") as logfile:
    if len(request) > 200:
      r = request[:200]
    else: r = request
    try:
      logfile.write("REQ: " 
                    + time.strftime("%d/%m/%Y %H:%M:%S ")
                    + r.encode("utf-8"))
    except UnicodeDecodeError:
      logfile.write("REQ: " 
                    + time.strftime("%d/%m/%Y %H:%M:%S ")
                    + r.encode('ascii', 'ignore'))
  os.system("echo \"$(tail -300 nasbot_ws.log)\"\
            > nasbot_ws.log")

def send_message(chat_id, text):
  requests.get(api_url
              + "sendMessage?parse_mode=Markdown&text=%s&chat_id=%s" 
              % (text, chat_id)) 

def on_ws_message(wsocket, message):
  with open("nasbot_ws.log", "a") as logfile:
    try:
      logfile.write("MSG: " 
                    + time.strftime("%d/%m/%Y %H:%M:%S ")
                    + message.encode("utf-8"))
    except UnicodeDecodeError:
      logfile.write("MSG: " 
                    + time.strftime("%d/%m/%Y %H:%M:%S ")
                    + message.encode('ascii', 'ignore'))
  os.system("echo \"$(tail -300 nasbot_ws.log)\"\
            > nasbot_ws.log")
  response = eval(message.replace("\\" ,""))
  global gid_chat
  global pending_magnet
  global dl_dirs
  if 'id' in response and 'result' in response:
    if "-pending" in response['id'] or \
       "-sp_magnet" in response['id']:
      gid = response['result']
      gid_chat[gid] = response['id']
    elif "-done" in response['id']:
      for k, v in gid_chat.iteritems():
        if response['id'] == v:
          text = "*Downloaded files:*\n\n"
          for file in response['result']:
            text += (file['path'] + "\n\n")
          chat_id = v.replace("-done", "")
          for k in dl_dirs.keys():
            text = text.replace(dl_dirs[k],
                                "In *'"+ k + "'* directory: ")
          if len(text) >= 300:
            text = text[:text.find("\n\n", 300)] + "...\n\netc, etc"
          send_message(chat_id, text.replace("_", " "))
          del gid_chat[k]
    elif "-started" in response['id']:
      if not type(response['result']) is list:
        gid = response['result']
        gid_chat[gid] = response['id']
        conductor(gid_chat[gid], "aria2.getFiles", '["%s"]' % gid)
      else:
        try:
          if response['result'][0]['uris'][0]['status'] == "waiting":
            text = "*Download is qued.* Files waiting:\n\n%s" % \
                    response['result'][0]['uris']\
                    [0]['uri']
            send_message(response['id'].replace("-started", ""), text)
          elif response['result'][0]['uris'][0]['status'] == "used":
            text = "*File downloading:*\n\n%s" % \
                    response['result'][0]['uris']\
                    [0]['uri']
            send_message(response['id'].replace("-started", ""), text)            
        except (IndexError, KeyError):
              text = "*Files downloading:*\n\n"
              for file in response['result']:
                text += (file['path'] + "\n\n")
              chat_id = response['id'].replace("-started", "")
              for k in dl_dirs.keys():
                text = text.replace(dl_dirs[k],
                                    "To *'"+ k + "'* directory: ")            
              if len(text) >= 300:
                text = text[:text.find("\n\n", 300)]\
                       + "...\n\netc, etc"
              send_message(chat_id, text.replace("_", " "))
    elif "-fail" in response['id']:
      try:
        text = "*Download from link failed:*\n\n%s" % \
                  response['result'][0]['uris'][0]['uri']
        send_message(response['id'].replace("-fail", ""), text)            
      except (IndexError, KeyError):
        text = "*Download of files failed:*\n\n"
        for file in response['result']:
          text += (file['path'] + "\n\n")
        chat_id = response['id'].replace("-fail", "")
        for k in dl_dirs.keys():
          text = text.replace(dl_dirs[k],
                              "To *'"+ k + "'* directory: ")            
        if len(text) >= 300:
          text = text[:text.find("\n\n", 300)]\
                 + "...\n\netc, etc"
        send_message(chat_id, text.replace("_", " "))
    else:
      gid_chat[response['result']] = response['id']
  elif 'id' in response and 'error' in response:
    position = response['id'].find("-sp_magnet")
    if position != -1:
      chat_id = response['id'][:position]
    else:
      chat_id = response['id'].replace("-started", "").replace(
                                       "-pending", "").replace(
                                       "-done", "")
    send_message(chat_id, response['error']['message'])
  elif response['method'] == "aria2.onDownloadComplete" or \
       response['method'] == "aria2.onBtDownloadComplete":
    gid = response['params'][0]['gid']
    if "-pending" in gid_chat[gid]:
      gid_chat[gid] = gid_chat[gid].replace("-pending", "")
      torrent_raw = open(pending_magnet[gid_chat[gid]]).read()
      download_torrent(gid_chat[gid] + "-started", torrent_raw)
      os.remove(pending_magnet[gid_chat[gid]])
      del pending_magnet[gid_chat[gid]]
      del gid_chat[gid]
    elif "-sp_magnet" in gid_chat[gid]:
      position = gid_chat[gid].find("-sp_magnet")
      download_dir = gid_chat[gid][position + 11:]
      gid_chat[gid] = gid_chat[gid][:position]
      try:
        torrent_b64 = base64.b64encode(open(pending_magnet\
                                    [gid_chat[gid]]).read())
      except (IndexError, AttributeError):
        send_message(gid_chat[gid], 
                    "Torrent info is corrupted.")
      conductor(gid_chat[gid] + "-started", "aria2.addTorrent",
             '["%s", [], {"dir":"%s"}]' % (torrent_b64, download_dir))
      os.remove(pending_magnet[gid_chat[gid]])
      del pending_magnet[gid_chat[gid]]
      del gid_chat[gid]
    elif "-started" in gid_chat[gid]:
      gid_chat[gid] = gid_chat[gid].replace("-started", "-done")
      conductor(gid_chat[gid], "aria2.getFiles", '["%s"]' % gid)
  elif response['method'] == "aria2.onDownloadError":
    gid = response['params'][0]['gid']
    position = gid_chat[gid].find("-sp_magnet")
    if position != -1:
      gid_chat[gid] = gid_chat[gid][:position] + "-fail"
    else:
      gid_chat[gid] = gid_chat[gid].replace("-started", "-fail"
                                            ).replace(
                                            "-pending", "-fail"
                                            ).replace(
                                            "-done", "-fail")
    conductor(gid_chat[gid], "aria2.getFiles", '["%s"]' % gid)
    del gid_chat[gid]
  id_store = shelve.open("id_file", writeback=True)
  id_store['gid_chat'], id_store['pending_magnet'] = \
  gid_chat, pending_magnet
  id_store.close()

def on_ws_error(wsocket, error):
  """
  TODO: depending on flavour of error have to 
  send error msg to master or log it to file
  """
  with open("nasbot_ws.log", "a") as logfile:
    try:
      logfile.write("ERR: "
                    + time.strftime("%d/%m/%Y %H:%M:%S")
                    + error.encode("utf-8"))
    except UnicodeDecodeError:
      logfile.write("ERR: " 
                    + time.strftime("%d/%m/%Y %H:%M:%S ")
                    + error.encode('ascii', 'ignore'))
  os.system("echo \"$(tail -300 nasbot_ws.log)\"\
            > nasbot_ws.log")

def on_ws_close(wsocket):
  thread.start_new_thread(wsocket.run_forever, ())

wsocket = websocket.WebSocketApp("ws://localhost:6800/jsonrpc",
                                  on_message = on_ws_message,
                                  on_error = on_ws_error,
                                  on_close = on_ws_close)

thread.start_new_thread(wsocket.run_forever, ())

def get_updates(offset):
  updates = []
  for msg in requests.get(api_url
                          + "getUpdates?timeout=100"
                          + offset).json()['result']:
    if 'message' in msg and \
       'text' in msg['message']:
      msg_text = msg['message']['text']
      user_id = msg['message']['from']
      chat_id = str(msg['message']['chat']['id'])
      if msg_text == "/help":
        global help_text
        send_message(chat_id, help_text)
      elif msg_text[:8] == "/special" and \
           str(user_id['id']) in masters:
        try:
          attr_list = msg_text[8:].replace(" ","").split(",")
          attr_list.insert(1, dl_dirs['General'])
          if attr_list[0][-8:] == ".torrent":
            try:
              attr_list[0] = base64.b64encode(requests.get(attr_list[0],
                                            stream=True).raw.read())
              conductor(chat_id + "-started", "aria2.addTorrent",
               '["%s", [], {"dir":"%s/%s"}]' % tuple(attr_list))
              send_message(chat_id, "Collecting metadata.")
            except (IndexError, AttributeError):
              send_message(chat_id, 
                          "Torrent info is corrupted.")
          elif attr_list[0][:8] == "magnet:?":
            id_store = shelve.open("id_file", writeback=True)
            try:
              pending_magnet[chat_id] = re.search(r"btih:(\w+)&?", 
                                     attr_list[0]).group(1).lower() \
                                     + ".torrent"
              conductor(chat_id + "-sp_magnet:" + attr_list[1] + "/"
                        + attr_list[2], "aria2.addUri",
                        '[["%s"], {"bt-metadata-only":"true",'\
                        '"bt-save-metadata":"true"}]' % attr_list[0])
              send_message(chat_id, "Collecting metadata.")
            except AttributeError:
              send_message(chat_id, "*It's not a magnet link:*\n\n%s"
                           % attr_list[0])
            id_store['pending_magnet'] = pending_magnet
            id_store.close()
          else:
            conductor(chat_id + "-started", "aria2.addUri",
             '[["%s"], {"dir":"%s/%s"}]' % tuple(attr_list))
        except TypeError:
          send_message(chat_id,
                      "Something wrong, maybe /help is needed?")
      else:
        updates.append([ chat_id, user_id, msg_text ])
    elif 'message' in msg and \
         'document' in msg['message'] and \
          str(msg['message']['from']['id']) in masters: 
      if msg['message']['document']['mime_type'] == \
         "application/x-bittorrent":
        uri = "https://api.telegram.org/file/bot%s/"\
              % token \
              + requests.get(
                api_url
                + "getFile?file_id="
                + msg['message']['document']['file_id']
                ).json()['result']['file_path']
        download_torrent(str(msg['message']['chat']['id'])
                         + "-started",
                         uri, uri=True)
    offset = "&offset=%d" % (msg['update_id'] + 1)
  return updates, offset

def dir_to_dl(link):
  global dl_dirs
  if re.findall(r"\.(avi|wmv|mkv|mov|m4v|mp4|mpeg|mpg)$",
                link, re.IGNORECASE|re.MULTILINE):
    if re.search(r"season|сезон|s\d\d?e\d\d?",
                 link, re.IGNORECASE|re.MULTILINE):
      download_dir = dl_dirs['Series']
    else:
      download_dir = dl_dirs['Movies']
  else:
    download_dir = dl_dirs['General']
  return download_dir

def download_torrent(chat_id, data, uri=False):
  if uri:
    torrent_raw = requests.get(data,
                  stream=True).raw.read()
  else: torrent_raw = data
  """
  gave up to parse files from bencoded string by myself
  so imported bencode module
  """
  try:
    torrent_b64 = base64.b64encode(torrent_raw)
    torrent_info = bencode.bdecode(torrent_raw)['info']
    files_list = ""
    if 'files' in torrent_info:
      for file in torrent_info['files']:
        files_list += str(file['path'][0]+"\n")
    else: files_list = str(torrent_info['name'])
    download_dir = dir_to_dl(files_list)
    conductor(chat_id, "aria2.addTorrent",
             '["%s", [], {"dir":"%s"}]' % (torrent_b64, download_dir))
  except (IndexError, AttributeError):
    send_message(chat_id.replace("-started", ""), 
                "Torrent info is corrupted.")

def parse_uri(updates):
  for msg in updates:
    if str(msg[1]['id']) in masters:
      uri = re.search(
            r"^(magnet\S+)|(\S\.torrent)$|^(http\S+|ftp\S+|sftp\S+)",
            msg[2])
      if uri:
        if uri.group(1):
          global pending_magnet
          id_store = shelve.open("id_file", writeback=True)
          try:
            pending_magnet[msg[0]] = re.search(r"btih:(\w+)&?", 
                                     uri.group(1)).group(1).lower() \
                                     + ".torrent"
            conductor(msg[0] + "-pending", "aria2.addUri",
                      '[["%s"], {"bt-metadata-only":"true",'\
                      '"bt-save-metadata":"true"}]' % uri.group(1))
            send_message(msg[0], "Collecting metadata.")
          except AttributeError:
            send_message(msg[0], "*It's not a magnet link:*\n\n%s."
                        % uri.group(1))
          id_store['pending_magnet'] = pending_magnet
          id_store.close()

        elif uri.group(2):
          download_torrent(msg[0] + "-started",
                           uri.group(2), uri=True)
        elif uri.group(3):
          download_dir = dir_to_dl(uri.group(3))
          conductor(msg[0] + "-started", "aria2.addUri",
                    '[["%s"], {"dir":"%s"}]' % (msg[2], download_dir))
      else:
        send_message(msg[0], "I can't do that.")
    else:
      send_message(msg[0], "Human, you'r not my master.")
      try:
        with open("nasbot_nonusers.log", "a") as logfile:
          logfile.write(msg.encode("utf-8"))
        os.system("echo \"$(tail -300 nasbot_nonusers.log)\"\
                  > nasbot_nonusers.log")
      except UnicodeDecodeError:
        pass

def main():
  offset = ""
  while True:
    updates, offset = get_updates(offset)
    if len(updates) > 0:
      parse_uri(updates)
    time.sleep(0.5)

if __name__ == '__main__':
    main()
