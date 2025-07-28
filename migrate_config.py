#!/usr/bin/env python3
"""
Migration script to convert existing vv.py configuration to the new web interface format
"""

import json
import os

def migrate_config():
    """Migrate existing configuration to new format"""
    
    # Read existing configuration from vv.py
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
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'Priority': 'u=0',
    }

    # Read existing data files
    destinataires = []
    if os.path.exists('destinataires.txt'):
        with open('destinataires.txt', 'r', encoding='utf-8') as f:
            destinataires = [line.strip() for line in f if line.strip()]

    subjects = []
    if os.path.exists('subjects.txt'):
        with open('subjects.txt', 'r', encoding='utf-8') as f:
            subjects = [line.strip() for line in f if line.strip()]

    froms = []
    if os.path.exists('froms.txt'):
        with open('froms.txt', 'r', encoding='utf-8') as f:
            froms = [line.strip() for line in f if line.strip()]

    # Create accounts.json
    account_data = {
        'id': 1,
        'name': 'Default Zoho Account',
        'cookies': cookies,
        'headers': headers,
        'org_id': '889488595',
        'created_at': '2024-01-01T00:00:00'
    }

    if not os.path.exists('accounts.json'):
        with open('accounts.json', 'w') as f:
            json.dump([account_data], f, indent=2)
        print("✅ Created accounts.json with default account")

    # Create campaigns.json with existing data
    if destinataires and subjects and froms:
        campaign_data = {
            'id': 1,
            'name': 'Migrated Campaign',
            'account_id': 1,
            'destinataires': '\n'.join(destinataires),
            'subjects': '\n'.join(subjects),
            'froms': '\n'.join(froms),
            'template_id': '6839465000000569041',  # From your original script
            'status': 'stopped',
            'created_at': '2024-01-01T00:00:00'
        }

        if not os.path.exists('campaigns.json'):
            with open('campaigns.json', 'w') as f:
                json.dump([campaign_data], f, indent=2)
            print("✅ Created campaigns.json with migrated campaign")
        else:
            print("ℹ️  campaigns.json already exists, skipping migration")

    print("\n🎉 Migration completed!")
    print("You can now start the web application with: python app.py")
    print("Default login: admin / admin123")

if __name__ == '__main__':
    migrate_config() 