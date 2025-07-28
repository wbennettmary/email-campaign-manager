import requests
import threading
import time
import random
from colorama import Fore, init
from queue import Queue

init(autoreset=True)

# === LECTURE DES FICHIERS ===
with open("destinataires.txt", "r", encoding="utf-8") as f:
    destinataires_list = [line.strip() for line in f if line.strip()]

with open("subjects.txt", "r", encoding="utf-8") as f:
    SUBJECTS = [line.strip() for line in f if line.strip()]

with open("froms.txt", "r", encoding="utf-8") as f:
    FROMS = [line.strip() for line in f if line.strip()]


# === CONFIG ===

cookies = {
    'ZohoMarkRef': '"https://www.zoho.com/crm/"',
    'ZohoMarkSrc': '"direct:crm^|direct:crm^|direct:crm"',
    'zsca63a3daff87f4d33b6cffbe7a949ff5f': '1748998504515zsc0.028101402882261373',
    'zft-sdc': 'isef%3Dtrue-isfr%3Dtrue-source%3Ddirect',
    'zps-tgr-dts': 'sc%3D1-expAppOnNewSession%3D%5B%5D-pc%3D1-sesst%3D1748998504516',
    'zohocrmmarketing-_zldp': 'YfEOFpfOAG91hdhAZ%2F9Z38S7%2F7Dm8LWciHLSiZglnOo4YJvx979yy3Ba8MR9w32Sf2G6cVQ2W%2Fc%3D',
    'zohocrmmarketing-_zldt': '6609f5b6-f874-4a97-94ca-973eac295a83-0',
    '_iamadt': 'bea8401a6ddee2b78829c4e5d357e4021a290cd87f116b6a4e4e799a3136d2606e573bf32991bbec5e713119abd9cca4',
    '_iambdt': 'cd0201d751667117a0c0f628f5ae0e211b022e5b55ed4556f6251cd87d6bbfac02d9f3acfe5bd5d0da7e20dfddd9248ab0a8a40b247035b47e90de37a897b45f',
    'dcl_pfx': 'us',
    'dcl_bd': 'zoho.com',
    'is_pfx': 'false',
    'zalb_6e4b8efee4': 'ce68e2ca044396e969b273c8a81c9836',
    'crmcsr': 'f632af6cc0cb84552c6ec6ea7bba239360d12aca0798287e6841666961d4692c0a0ace27b1682352bd1f95e54d66fa84eb778e71aa65260352d11bb66ea26364',
    '_zcsr_tmp': 'f632af6cc0cb84552c6ec6ea7bba239360d12aca0798287e6841666961d4692c0a0ace27b1682352bd1f95e54d66fa84eb778e71aa65260352d11bb66ea26364',
    'CROSSCDNID': 'd43ba3328986d1923c6c81b3ace64c01d46f08fb4c0fb1e1bf19c73b60d4407911f18bef25c690d72c501d4d13b15e3d',
    'CROSSCDNCOUNTRY': 'MA',
    'JSESSIONID': '2A58A608E1A9D32505AC79240DD6E49A',
    'zalb_8b7213828d': 'cb9b85e4a61a657d036913e6557d8fdf',
    'CSRF_TOKEN': 'f632af6cc0cb84552c6ec6ea7bba239360d12aca0798287e6841666961d4692c0a0ace27b1682352bd1f95e54d66fa84eb778e71aa65260352d11bb66ea26364',
    'zalb_3309580ed5': '75960725d24591cd13168c14f2de180e',
    'CT_CSRF_TOKEN': 'f632af6cc0cb84552c6ec6ea7bba239360d12aca0798287e6841666961d4692c0a0ace27b1682352bd1f95e54d66fa84eb778e71aa65260352d11bb66ea26364',
    'wms-tkp-token': '889495507-a59762fc-5eba325046653556f52bde2500ddc622',
    'zohocares-_zldp': 'YfEOFpfOAG84VyFwO4%2BLoHZoX%2F0CZR0VYPbhO5m8mONEYIiQ5gOxoxPxU1hyCs%2BJf2G6cVQ2W%2Fc%3D',
    'zohocares-_zldt': '1e0ab63f-e9d3-4a2e-8a62-7d3e3a24bc9f-0',
    'com_chat_owner': '1748998734853',
    'com_avcliq_owner': '1748998734854',
    'drecn': 'f632af6cc0cb84552c6ec6ea7bba239360d12aca0798287e6841666961d4692c0a0ace27b1682352bd1f95e54d66fa84eb778e71aa65260352d11bb66ea26364',
    'showEditorLeftPane': 'undefined',
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.5',
    # 'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Referer': 'https://crm.zoho.com/',
    'X-ZCSRF-TOKEN': 'crmcsrfparam=f632af6cc0cb84552c6ec6ea7bba239360d12aca0798287e6841666961d4692c0a0ace27b1682352bd1f95e54d66fa84eb778e71aa65260352d11bb66ea26364',
    'Content-type': 'application/json; charset=utf-8',
    'X-CRM-ORG': '889488595',
    'X-Requested-With': 'XMLHttpRequest',
    'X-Client-SubVersion': '20f107dee180be4805f9de908b0e0762',
    'X-Static-Version': '10715012',
    'x-my-normurl': 'crm.settings.section.workflow-rules.create-workflow-rule',
    'Origin': 'https://crm.zoho.com',
    'DNT': '1',
    'Sec-GPC': '1',
    'Connection': 'keep-alive',
    # 'Cookie': 'ZohoMarkRef="https://www.zoho.com/crm/"; ZohoMarkSrc="direct:crm^|direct:crm^|direct:crm"; zsca63a3daff87f4d33b6cffbe7a949ff5f=1748998504515zsc0.028101402882261373; zft-sdc=isef%3Dtrue-isfr%3Dtrue-source%3Ddirect; zps-tgr-dts=sc%3D1-expAppOnNewSession%3D%5B%5D-pc%3D1-sesst%3D1748998504516; zohocrmmarketing-_zldp=YfEOFpfOAG91hdhAZ%2F9Z38S7%2F7Dm8LWciHLSiZglnOo4YJvx979yy3Ba8MR9w32Sf2G6cVQ2W%2Fc%3D; zohocrmmarketing-_zldt=6609f5b6-f874-4a97-94ca-973eac295a83-0; _iamadt=bea8401a6ddee2b78829c4e5d357e4021a290cd87f116b6a4e4e799a3136d2606e573bf32991bbec5e713119abd9cca4; _iambdt=cd0201d751667117a0c0f628f5ae0e211b022e5b55ed4556f6251cd87d6bbfac02d9f3acfe5bd5d0da7e20dfddd9248ab0a8a40b247035b47e90de37a897b45f; dcl_pfx=us; dcl_bd=zoho.com; is_pfx=false; zalb_6e4b8efee4=ce68e2ca044396e969b273c8a81c9836; crmcsr=f632af6cc0cb84552c6ec6ea7bba239360d12aca0798287e6841666961d4692c0a0ace27b1682352bd1f95e54d66fa84eb778e71aa65260352d11bb66ea26364; _zcsr_tmp=f632af6cc0cb84552c6ec6ea7bba239360d12aca0798287e6841666961d4692c0a0ace27b1682352bd1f95e54d66fa84eb778e71aa65260352d11bb66ea26364; CROSSCDNID=d43ba3328986d1923c6c81b3ace64c01d46f08fb4c0fb1e1bf19c73b60d4407911f18bef25c690d72c501d4d13b15e3d; CROSSCDNCOUNTRY=MA; JSESSIONID=2A58A608E1A9D32505AC79240DD6E49A; zalb_8b7213828d=cb9b85e4a61a657d036913e6557d8fdf; CSRF_TOKEN=f632af6cc0cb84552c6ec6ea7bba239360d12aca0798287e6841666961d4692c0a0ace27b1682352bd1f95e54d66fa84eb778e71aa65260352d11bb66ea26364; zalb_3309580ed5=75960725d24591cd13168c14f2de180e; CT_CSRF_TOKEN=f632af6cc0cb84552c6ec6ea7bba239360d12aca0798287e6841666961d4692c0a0ace27b1682352bd1f95e54d66fa84eb778e71aa65260352d11bb66ea26364; wms-tkp-token=889495507-a59762fc-5eba325046653556f52bde2500ddc622; zohocares-_zldp=YfEOFpfOAG84VyFwO4%2BLoHZoX%2F0CZR0VYPbhO5m8mONEYIiQ5gOxoxPxU1hyCs%2BJf2G6cVQ2W%2Fc%3D; zohocares-_zldt=1e0ab63f-e9d3-4a2e-8a62-7d3e3a24bc9f-0; com_chat_owner=1748998734853; com_avcliq_owner=1748998734854; drecn=f632af6cc0cb84552c6ec6ea7bba239360d12aca0798287e6841666961d4692c0a0ace27b1682352bd1f95e54d66fa84eb778e71aa65260352d11bb66ea26364; showEditorLeftPane=undefined',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Priority': 'u=0',
}

# === QUEUE THREAD-SAFE ===
email_queue = Queue()
for email in destinataires_list:
    email_queue.put(email)

lock = threading.Lock()
counter = 0

# === FONCTION THREAD ===
def send_email_worker():
    global counter
    while not email_queue.empty():
        destinataire = email_queue.get()

        subject = random.choice(SUBJECTS)
        sender = random.choice(FROMS)

        # Génération du script Deluge
        script = f'''void automation.Send_Email_Template1()
{{
    curl = "https://www.zohoapis.com/crm/v7/settings/email_templates/6839465000000569041";

    getTemplate = invokeurl
    [
        url: curl
        type: GET
        connection: "re"
    ];

    EmailTemplateContent = getTemplate.get("email_templates").get(0).get("content");

    destinataires = list();
    destinataires.add("{destinataire}");

    sendmail
    [
        from: "{sender} <" + zoho.loginuserid + ">"
        to: destinataires
        subject: "{subject}"
        message: EmailTemplateContent
    ];
}}'''

        json_data = {
            'functions': [
                {
                    'script': script,
                    'arguments': {},
                },
            ],
        }

        try:
            response = requests.post(
                'https://crm.zoho.com/crm/v7/settings/functions/send_email_template/actions/test',
                cookies=cookies,
                headers=headers,
                json=json_data,
                timeout=15
            )

            with lock:
                counter += 1
                if response.status_code == 200:
                    print(Fore.GREEN + f"✅ [{counter}] Email envoyé à {destinataire}")
                else:
                    print(Fore.RED + f"❌ [{counter}] Échec à {destinataire} (Status {response.status_code})")

                if counter % 10 == 0:
                    print(Fore.CYAN + f"⏸️  Pause 5 secondes après {counter} mails...")
                    time.sleep(15)

        except Exception as e:
            with lock:
                counter += 1
                print(Fore.RED + f"❌ [{counter}] Erreur à {destinataire} - {e}")

        time.sleep(1)
        email_queue.task_done()

# === LANCEMENT DES THREADS ===
THREAD_COUNT = 1  # 🔁 Augmente si tu veux envoyer plus rapidement
threads = []

for _ in range(THREAD_COUNT):
    t = threading.Thread(target=send_email_worker)
    t.start()
    threads.append(t)

for t in threads:
    t.join()

print(Fore.YELLOW + f"\n✅ Tous les emails ont été traités.")
