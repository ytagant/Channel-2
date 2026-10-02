import os
import json
import subprocess
import time
import re
import random
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

DRIVE_FOLDER_ID = os.environ.get('DRIVE_FOLDER_ID')
SERVICE_ACCOUNT_JSON = os.environ.get('SERVICE_ACCOUNT_JSON')

with open('service_account.json', 'w') as f:
    f.write(SERVICE_ACCOUNT_JSON)

creds_drive = service_account.Credentials.from_service_account_file(
    'service_account.json', scopes=['https://www.googleapis.com/auth/drive']
)
drive_service = build('drive', 'v3', credentials=creds_drive)

# 🌟 नया फंक्शन: अपलोड के बाद फाइल सेव करने के लिए फोल्डर बनाना या ढूंढना 🌟
def get_or_create_success_folder():
    query = f"name = 'Uploaded_Success' and mimeType = 'application/vnd.google-apps.folder' and '{DRIVE_FOLDER_ID}' in parents and trashed = false"
    for attempt in range(4):
        try:
            results = drive_service.files().list(q=query, fields="files(id, name)").execute()
            files = results.get('files', [])
            if files:
                return files[0]['id'] 
            else:
                folder_metadata = {
                    'name': 'Uploaded_Success',
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [DRIVE_FOLDER_ID]
                }
                folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
                print("📁 नया 'Uploaded_Success' फोल्डर बना दिया गया है।")
                return folder.get('id')
        except Exception as e:
            if attempt == 3: return None
            time.sleep(10)

# 🌟 नया फंक्शन: फाइल को डिलीट करने के बजाय फोल्डर में मूव करना 🌟
def move_file_to_success_folder(file_id, success_folder_id):
    if not success_folder_id: return
    for attempt in range(4):
        try:
            file = drive_service.files().get(fileId=file_id, fields='parents').execute()
            previous_parents = ",".join(file.get('parents', []))
            
            drive_service.files().update(
                fileId=file_id,
                addParents=success_folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
            print(f"📦 फाइल (ID: {file_id}) को 'Uploaded_Success' फोल्डर में मूव कर दिया गया है।")
            return
        except Exception as e:
            if attempt == 3: return
            time.sleep(10)

def download_from_drive(file_id, output_path):
    print(f"📥 गूगल ड्राइव से फाइल {output_path} डाउनलोड की जा रही है...")
    for attempt in range(4):
        try:
            request = drive_service.files().get_media(fileId=file_id)
            with open(output_path, 'wb') as f:
                f.write(request.execute())
            print("✅ डाउनलोड मुकम्मल हो गया!")
            return
        except Exception as e:
            print(f"⚠️ डाउनलोड नेटवर्क एरर (कोशिश {attempt+1}/4): {e}")
            if attempt == 3: raise e
            time.sleep(10)

def edit_anti_copyright_full_video(input_video, output_video):
    print("🎬 मुकम्मल वीडियो प्रोसेसिंग: FFmpeg के ज़रिये एंटी-कॉपीराइट फिल्टर्स लगाए जा रहे हैं...")
    video_filter = (
        "crop=iw-2:ih-2:1:1,scale=iw:ih,"
        "eq=brightness=0.01:contrast=1.04:saturation=1.08,"
        "unsharp=5:5:0.8:3:3:0.4,"
        "noise=alls=5:allf=t+u,"
        "drawbox=enable='lt(mod(t,12),0.02)':x=0:y=0:w=iw:h=ih:color=black@0.12:t=fill"
    )
    cmd = [
        'ffmpeg', '-y',
        '-i', input_video,
        '-vf', video_filter,
        '-af', "loudnorm=I=-16:TP=-1.5:LRA=11",
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28',
        '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '128k',
        output_video
    ]
    subprocess.run(cmd, check=True)
    print("✨ मुकम्मल वीडियो की एंटी-कॉपीराइट एडिटिंग पूरी हो गई!")

def enhance_and_upload_thumbnail(youtube, video_id, thumbnail_filename, success_folder_id):
    t_id = get_file_id_by_name(thumbnail_filename)
    if not t_id: return
    download_from_drive(t_id, 'raw_thumb.jpg')
    
    print("🎨 FFmpeg के ज़रिये थंबनेल को यूनिक (Unique) बनाया जा रहा है...")
    thumb_filter = "crop=iw*0.96:ih*0.96,scale=iw:ih,eq=brightness=0.02:contrast=1.08:saturation=1.1,noise=alls=2:allf=t+u,unsharp=3:3:0.5"
    cmd = [
        'ffmpeg', '-y',
        '-i', 'raw_thumb.jpg',
        '-vf', thumb_filter,
        '-q:v', '2',
        'edited_thumb.jpg'
    ]
    try:
        subprocess.run(cmd, check=True)
        print("✨ थंबनेल कामयाबी से यूनिक हो गया!")
    except Exception as e:
        print(f"⚠️ थंबनेल एडिट करने में एरर, असल थंबनेल इस्तेमाल किया जा रहा है: {e}")
        os.rename('raw_thumb.jpg', 'edited_thumb.jpg')
    
    for attempt in range(4):
        try:
            media = MediaFileUpload('edited_thumb.jpg', mimetype='image/jpeg')
            youtube.thumbnails().set(videoId=video_id, media_body=media).execute()
            print("✅ एडिट किया गया थंबनेल YouTube पर अपलोड हो गया!")
            # 🌟 थंबनेल को भी सक्सेस फोल्डर में मूव करना 🌟
            if success_folder_id: move_file_to_success_folder(t_id, success_folder_id)
            return
        except Exception as e:
            if attempt == 3: return
            time.sleep(10)

def get_file_id_by_name(filename):
    query = f"name = '{filename}' and '{DRIVE_FOLDER_ID}' in parents and trashed = false"
    for attempt in range(4):
        try:
            results = drive_service.files().list(q=query, fields="files(id, name)").execute()
            files = results.get('files', [])
            return files[0]['id'] if files else None
        except Exception as e:
            if attempt == 3: return None
            time.sleep(10)

def get_youtube_service():
    cs_id = get_file_id_by_name('client_secret.json')
    tk_id = get_file_id_by_name('token.json')
    if not cs_id or not tk_id: raise Exception("❌ client_secret.json या token.json ड्राइव में नहीं मिला!")
    download_from_drive(cs_id, 'client_secret.json')
    download_from_drive(tk_id, 'token.json')

    with open('client_secret.json', 'r') as f: client_secret_data = json.load(f)
    with open('token.json', 'r') as f: token_data = json.load(f)
    client_info = client_secret_data.get('web') or client_secret_data.get('installed')

    creds_yt = Credentials(
        token=token_data.get('token'), refresh_token=token_data.get('refresh_token'),
        token_uri=client_info.get('token_uri', 'https://oauth2.googleapis.com/token'), 
        client_id=client_info['client_id'],
        client_secret=client_info['client_secret'], scopes=token_data.get('scopes')
    )
    
    if not creds_yt.valid:
        if creds_yt.expired and creds_yt.refresh_token:
            for attempt in range(4):
                try:
                    creds_yt.refresh(Request())
                    print("🔄 YouTube का टोकन एक्सपायर हो गया था, नया टोकन जनरेट कर लिया गया है!")
                    
                    token_data['token'] = creds_yt.token
                    with open('token.json', 'w') as f: json.dump(token_data, f)
                    
                    media = MediaFileUpload('token.json', mimetype='application/json')
                    drive_service.files().update(fileId=tk_id, media_body=media).execute()
                    print("✅ नया टोकन ड्राइव पर अपडेट कर दिया गया है!")
                    break
                except Exception as e:
                    if attempt == 3: raise e
                    time.sleep(10)
                    
    return build('youtube', 'v3', credentials=creds_yt)

def get_strict_asian_proxies():
    print("🔍 इंटरनेट से सिर्फ आला क्वालिटी की एशियन प्रॉक्सी (भारत, पाकिस्तान, UAE, बांग्लादेश) तलाशी जा रही हैं...")
    url = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=IN,PK,AE,BD&ssl=yes&anonymity=elite"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            proxies = response.text.strip().split('\r\n')
            valid_proxies = [p for p in proxies if p]
            print(f"✅ कुल {len(valid_proxies)} एशियन प्रॉक्सी मिल गईं!")
            return valid_proxies
    except Exception as e:
        print(f"⚠️ प्रॉक्सी तलाश करने में एरर: {e}")
    return []

def verify_ip_cleanliness(proxy_ip):
    ip_only = proxy_ip.split(':')[0]
    verify_url = f"http://ip-api.com/json/{ip_only}?fields=status,country,countryCode,hosting"
    try:
        res = requests.get(verify_url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                valid_countries = ['IN', 'PK', 'AE', 'BD']
                if data.get("countryCode") not in valid_countries:
                    return False, f"बाहरी देश ({data.get('country')})"
                if data.get("hosting") == True:
                    return False, "डेटा सेंटर/स्पैम IP"
                return True, data.get("country")
    except:
        pass
    return False, "चेक फेल (प्रॉक्सी डेड है)"

# 🌟 नया फंक्शन: चैनल की प्लेलिस्ट में तुरंत चेक करेगा (सर्च API का इंतज़ार नहीं करेगा) 🌟
def check_if_video_uploaded(youtube, title):
    try:
        channel_req = youtube.channels().list(part="contentDetails", mine=True).execute()
        uploads_playlist = channel_req['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        playlist_req = youtube.playlistItems().list(part="snippet", playlistId=uploads_playlist, maxResults=5).execute()
        for vid_item in playlist_req.get('items', []):
            if vid_item['snippet']['title'] == title:
                return vid_item['snippet']['resourceId']['videoId']
    except Exception as e:
        print(f"⚠️ Playlist check error: {e}")
    return None

def main():
    success_folder_id = get_or_create_success_folder()

    queue_file_id = get_file_id_by_name('queue.json')
    if not queue_file_id: return
    download_from_drive(queue_file_id, 'queue.json')

    with open('queue.json', 'r', encoding='utf-8') as f: queue = json.load(f)
    if not queue: return

    history = []
    history_file_id = get_file_id_by_name('processed_history.json')
    if history_file_id:
        download_from_drive(history_file_id, 'processed_history.json')
        try:
            with open('processed_history.json', 'r', encoding='utf-8') as f: history = json.load(f)
        except: pass

    item = None
    while queue:
        if queue[0]['filename'] in history: queue.pop(0)
        elif not get_file_id_by_name(queue[0]['filename']):
            history.append(queue[0]['filename'])
            queue.pop(0)
        else:
            item = queue.pop(0)
            break

    with open('queue.json', 'w', encoding='utf-8') as f: json.dump(queue, f, indent=4)
    for attempt in range(4):
        try:
            drive_service.files().update(fileId=queue_file_id, media_body=MediaFileUpload('queue.json')).execute()
            break
        except Exception:
            if attempt == 3: raise
            time.sleep(10)

    if not item: return

    print(f"\n🚀 प्रोसेसिंग शुरू: {item['title']}")
    video_id = get_file_id_by_name(item['filename'])
    download_from_drive(video_id, 'raw_video.mp4')
    
    edit_anti_copyright_full_video('raw_video.mp4', 'edited_video.mp4')

    final_title = f"{item['title']} \u200B"
    tags_list = item.get('tags', [])
    if tags_list: random.shuffle(tags_list)

    original_desc = item.get('description', '')
    clean_desc = re.sub(r'http[s]?://\S+|www\.\S+', '', original_desc)
    clean_desc = re.sub(r'\n\s*\n', '\n\n', clean_desc).strip()
    
    disclaimer_text = (
        "⚠️ Copyright Disclaimer:\n"
        "Under section 107 of the Copyright Act 1976, allowance is made for 'fair use' "
        "for purposes such as criticism, comment, news reporting, teaching, scholarship, and research."
    )
    
    if "disclaimer" not in clean_desc.lower() and "copyright" not in clean_desc.lower():
        clean_desc = f"{clean_desc}\n\n{disclaimer_text}"
        
    credit_section = ""
    orig_url = item.get('webpage_url') or item.get('original_url')
    orig_channel = item.get('uploader') or item.get('channel')
    
    if orig_channel and orig_url:
        credit_section = f"\n\n🎥 वीडियो क्रेडिट (Video Credit): {orig_channel}\n🔗 असल लिंक (Original): {orig_url}"
    elif orig_channel:
        credit_section = f"\n\n🎥 वीडियो क्रेडिट (Video Credit): {orig_channel}"
    elif orig_url:
        credit_section = f"\n\n🎥 वीडियो क्रेडिट (Video Credit): {orig_url}"
    else:
        credit_section = "\n\n🎥 वीडियो क्रेडिट (Credit): Respective Owner"

    formatted_description = f"{clean_desc}\n\n{item.get('hashtags', '')}{credit_section}".strip()
    
    body = {
        'snippet': {
            'title': final_title,
            'description': formatted_description,
            'tags': tags_list,
            'categoryId': '24'
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False,
        }
    }

    upload_success = False
    max_master_retries = 3 # इसे 5 से 3 कर दिया है ताकि सर्वर ज़्यादा लोड न ले  
    youtube = None
    
    try:
        youtube = get_youtube_service()
    except Exception as e:
        print(f"❌ YouTube ऑथेंटिकेशन फेल: {e}")
        return

    for master_attempt in range(max_master_retries):
        if upload_success: break
            
        print(f"\n🔄 नेटवर्क/प्रॉक्सी राउंड {master_attempt + 1}/{max_master_retries} शुरू...")
        asian_proxies = get_strict_asian_proxies()
        if not asian_proxies:
            print("⚠️ कोई एशियन प्रॉक्सी नहीं मिली। डायरेक्ट नेटवर्क ट्राई कर रहे हैं...")
            asian_proxies = ['direct']

        for proxy in asian_proxies:
            if upload_success: break

            # 🌟 1. अपलोड से पहले सिक्योरिटी चेक 🌟
            print("🔍 सिक्योरिटी चेक: चेक किया जा रहा है कि क्या वीडियो पहले से अपलोड हो चुकी है...")
            vid_id = check_if_video_uploaded(youtube, final_title)
            if vid_id:
                print(f"✅ सुरक्षित रोक: यह वीडियो चैनल पर पहले से मौजूद है! (ID: {vid_id}) डुप्लीकेट को रोक दिया गया।")
                upload_success = True
                break

            country_info = ""
            if proxy != 'direct':
                is_clean, country_info = verify_ip_cleanliness(proxy)
                if not is_clean:
                    print(f"🚫 प्रॉक्सी रिजेक्ट कर दी गई ({country_info}): {proxy}")
                    continue
                
                print(f"🌐 टेस्ट की जा रही है क्लीन एशियन प्रॉक्सी ({country_info}): {proxy}")
                os.environ['http_proxy'] = f"http://{proxy}"
                os.environ['https_proxy'] = f"http://{proxy}"
            else:
                print("🌐 डायरेक्ट अपलोड (बिना प्रॉक्सी) ट्राई कर रहे हैं...")
                os.environ.pop('http_proxy', None)
                os.environ.pop('https_proxy', None)

            try:
                media = MediaFileUpload('edited_video.mp4', chunksize=-1, resumable=True)
                request = youtube.videos().insert(part=','.join(body.keys()), body=body, media_body=media)
                
                # 🌟 2. अंधा लूप (range(4)) यहाँ से पूरी तरह हटा दिया गया है 🌟
                try:
                    response = request.execute()
                    print(f"🎉 मुकम्मल वीडियो अपलोड हो गई! ID: {response['id']}")
                    vid_id = response['id']
                    
                    print("\n" + "="*60)
                    if proxy != 'direct':
                        print(f"🚀 SUCCESS LOG: यह वीडियो कामयाबी के साथ {proxy} ({country_info}) के IP से अपलोड हो गई है!")
                    else:
                        print(f"🚀 SUCCESS LOG: यह वीडियो कामयाबी के साथ डायरेक्ट गिटहब IP से अपलोड हो गई है!")
                    print("="*60 + "\n")
                    
                    upload_success = True
                except Exception as e:
                    print(f"⚠️ अपलोड के दौरान कनेक्शन टूटा (Error: {e})")
                    
                    # 🌟 3. नया अपडेट: 5 मिनट (300 सेकंड) का टाइमर 🌟
                    print("⏳ प्रॉक्सी डिस्कनेक्ट हो गई! मुमकिन है आधी अपलोड के बाद वीडियो सर्वर पर चली गई हो।")
                    print("🔍 स्मार्ट चेकिंग: YouTube प्रोसेसिंग के लिए 5 मिनट (300 सेकंड) का इंतज़ार किया जा रहा है...")
                    time.sleep(300) 
                    
                    temp_http = os.environ.pop('http_proxy', None)
                    temp_https = os.environ.pop('https_proxy', None)
                    
                    # 5 मिनट बाद चैनल की प्लेलिस्ट में चेक
                    vid_id = check_if_video_uploaded(youtube, final_title)
                    
                    if temp_http: os.environ['http_proxy'] = temp_http
                    if temp_https: os.environ['https_proxy'] = temp_https

                    if vid_id:
                        print(f"🎉 स्मार्ट चेक पास! प्रॉक्सी एरर के बावजूद वीडियो बैकग्राउंड में अपलोड हो चुकी थी! ID: {vid_id}")
                        upload_success = True
                    else:
                        print("⚠ 5 मिनट इंतज़ार के बाद भी चैनल पर वीडियो नहीं मिली। अब अगली प्रॉक्सी से दोबारा अपलोड शुरू किया जाएगा।")

                if upload_success:
                    if 'thumbnail' in item: 
                        enhance_and_upload_thumbnail(youtube, vid_id, item['thumbnail'], success_folder_id)
                    
                    # 🌟 4. कामयाबी की सूरत में वीडियो को डिलीट करने के बजाय मूव करें 🌟
                    if success_folder_id: move_file_to_success_folder(video_id, success_folder_id)
                    
                    if item['filename'] not in history: history.append(item['filename'])
                    with open('processed_history.json', 'w', encoding='utf-8') as f: json.dump(history, f, indent=4)
                    mh = MediaFileUpload('processed_history.json')
                    if history_file_id: drive_service.files().update(fileId=history_file_id, media_body=mh).execute()
                    else: drive_service.files().create(body={'name':'processed_history.json','parents':[DRIVE_FOLDER_ID]}, media_body=mh).execute()
                    
                    break # प्रॉक्सी लूप ब्रेक कर दें
                    
            except Exception as e:
                print(f"❌ प्रॉक्सी {proxy} फेल हो गई: {e} | अगली ट्राई कर रहे हैं...")
                
        if not upload_success:
            print("⏳ तमाम प्रॉक्सी फेल हो गईं। 15 सेकंड इंतज़ार के बाद इंटरनेट से नई प्रॉक्सी तलाशी जाएंगी...")
            os.environ.pop('http_proxy', None)
            os.environ.pop('https_proxy', None)
            time.sleep(15)

    if not upload_success:
        print("\n⚠ तमाम प्रॉक्सी ट्राई करने के बावजूद वीडियो अपलोड नहीं हो सकी।")
        if item['filename'] not in history:
            history.append(item['filename'])
            with open('processed_history.json', 'w', encoding='utf-8') as f: 
                json.dump(history, f, indent=4)
            mh = MediaFileUpload('processed_history.json')
            if history_file_id: 
                drive_service.files().update(fileId=history_file_id, media_body=mh).execute()
            else:
                drive_service.files().create(body={'name':'processed_history.json','parents':[DRIVE_FOLDER_ID]}, media_body=mh).execute()

    os.environ.pop('http_proxy', None)
    os.environ.pop('https_proxy', None)

    for file in ['raw_video.mp4', 'edited_video.mp4', 'raw_thumb.jpg', 'edited_thumb.jpg', 'client_secret.json', 'token.json', 'service_account.json']:
        if os.path.exists(file): os.remove(file)

if __name__ == '__main__':
    main()
