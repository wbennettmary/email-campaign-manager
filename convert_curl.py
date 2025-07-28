#!/usr/bin/env python3
"""
Convert cURL command to JSON format for web interface
"""

import json
import re

def convert_curl_to_json(curl_command):
    """Convert cURL command to JSON format"""
    
    # Extract cookies from -b parameter
    cookies = {}
    cookie_match = re.search(r"-b '([^']+)'", curl_command)
    if cookie_match:
        cookie_string = cookie_match.group(1)
        for cookie in cookie_string.split(';'):
            cookie = cookie.strip()
            if '=' in cookie:
                name, value = cookie.split('=', 1)
                cookies[name.strip()] = value.strip()
    
    # Extract headers from -H parameters
    headers = {}
    header_matches = re.findall(r"-H '([^:]+): ([^']+)'", curl_command)
    for name, value in header_matches:
        headers[name] = value
    
    # Extract organization ID
    org_id = headers.get('x-crm-org', 'Not found')
    
    return cookies, headers, org_id

# Your cURL command
curl_command = """curl 'https://crm.zoho.com/crm/v7/settings/functions/send_email_template1/actions/test' \\
  -H 'accept: application/json' \\
  -H 'accept-language: en-US,en;q=0.9' \\
  -H 'content-type: application/json; charset=UTF-8' \\
  -b 'zalb_6e4b8efee4=d962f19b54ad31880cd346e84c4de522; _iamadt=cbdadbabbd4c7c525be2b2ac2ebb645adf4539c6eb8744fea5733068de9545fd197877248a4b7d9a157d0fa65e6aa27a; _iambdt=f0b4a0c2ae471187991a11ec38be2842a33a11fcecb317185a52a389132be31a094d747db129bd2d96140e599d1096523aee6af729a98d9ea91c40ce13dff488; dcl_pfx=us; dcl_bd=zoho.com; is_pfx=false; crmcsr=436130b1a47a6d1fc02b8c1300d312496df38852803b4e2e8848146f213a8a675691e0a375c3393c99cabc7f19616c0fd200fb2a90a2be36d54dc9ff6f48945f; _zcsr_tmp=436130b1a47a6d1fc02b8c1300d312496df38852803b4e2e8848146f213a8a675691e0a375c3393c99cabc7f19616c0fd200fb2a90a2be36d54dc9ff6f48945f; CROSSCDNCOUNTRY=MA; zalb_8b7213828d=12e72725b02392af3450b3068735156e; CSRF_TOKEN=436130b1a47a6d1fc02b8c1300d312496df38852803b4e2e8848146f213a8a675691e0a375c3393c99cabc7f19616c0fd200fb2a90a2be36d54dc9ff6f48945f; zalb_3309580ed5=3b795eb40962db47c5834d24ffabe50e; CT_CSRF_TOKEN=436130b1a47a6d1fc02b8c1300d312496df38852803b4e2e8848146f213a8a675691e0a375c3393c99cabc7f19616c0fd200fb2a90a2be36d54dc9ff6f48945f; wms-tkp-token=893594413-de04d5db-2029b85d7edea0696c9884a6c80fd8d4; zohocares-_zldp=YfEOFpfOAG99ex08PWH5hjrw70TPStpEG%2BNuuzfVUSOoqOLpKQisT64yV9FwKlUUJ1pABzohHZA%3D; zohocares-_zldt=a685de70-020d-45a5-92bb-dfae401a4a22-0; drecn=436130b1a47a6d1fc02b8c1300d312496df38852803b4e2e8848146f213a8a675691e0a375c3393c99cabc7f19616c0fd200fb2a90a2be36d54dc9ff6f48945f; JSESSIONID=E6B5A2D0DB934487BEA889F21E5B033B; showEditorLeftPane=undefined; CROSSCDNID=0dfc7a7294482f0279828b976012559d1cf0b7ee3c59b155e6c560ad2435d5a055420932844f716404b8a629920d5ab3; com_chat_owner=1752684773545; com_avcliq_owner=1752684773546' \\
  -H 'origin: https://crm.zoho.com' \\
  -H 'priority: u=1, i' \\
  -H 'referer: https://crm.zoho.com/' \\
  -H 'sec-ch-ua: "Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"' \\
  -H 'sec-ch-ua-mobile: ?0' \\
  -H 'sec-ch-ua-platform: "Windows"' \\
  -H 'sec-fetch-dest: empty' \\
  -H 'sec-fetch-mode: cors' \\
  -H 'sec-fetch-site: same-origin' \\
  -H 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36' \\
  -H 'x-client-subversion: 78af65b8a40a4dd19f56b1546e7caa4a' \\
  -H 'x-crm-org: 893592226' \\
  -H 'x-my-normurl: crm.settings.section.workflow-rules.create-workflow-rule' \\
  -H 'x-requested-with: XMLHttpRequest' \\
  -H 'x-static-version: 11040330' \\
  -H 'x-zcsrf-token: crmcsrfparam=436130b1a47a6d1fc02b8c1300d312496df38852803b4e2e8848146f213a8a675691e0a375c3393c99cabc7f19616c0fd200fb2a90a2be36d54dc9ff6f48945f' \\
  --data-raw '{"functions":[{"script":"void automation.Send_Email_Template1()\\n{\\n    curl = \\"https://www.zohoapis.com/crm/v7/settings/email_templates/6896719000000573259\\";\\n\\n    getTemplate = invokeurl\\n    [\\n        url: curl\\n        type: GET\\n        connection: \\"re\\"\\n    ];\\n\\n    EmailTemplateContent = getTemplate.get(\\"email_templates\\").get(0).get(\\"content\\");\\n\\n    // Liste des destinataires\\n    destinataires = list();\\n    destinataires.add(\\"jaafarmoon@hotmail.com\\");\\n    destinataires.add(\\"faouzia_hammam@hotmail.fr\\");\\n    destinataires.add(\\"moonmjk94@gmail.com\\");\\n\\n    sendmail\\n    [\\n        from: \\"cc <\\" + zoho.loginuserid + \\">\\"\\n        to: destinataires\\n        subject: \\"Baisse\\"\\n        message: EmailTemplateContent\\n    ];\\n}","arguments":{}}]}'"""

print("🔧 Converting cURL to JSON format...")
print("=" * 50)

cookies, headers, org_id = convert_curl_to_json(curl_command)

print("✅ CONVERSION COMPLETE!")
print("\n" + "=" * 50)
print("📋 COPY THESE VALUES TO YOUR WEB INTERFACE:")
print("=" * 50)

print("\n🎯 ORGANIZATION ID:")
print(org_id)

print("\n🍪 COOKIES (JSON):")
print(json.dumps(cookies, indent=2))

print("\n📋 HEADERS (JSON):")
print(json.dumps(headers, indent=2))

print("\n" + "=" * 50)
print("📝 INSTRUCTIONS:")
print("1. Go to your web interface: http://localhost:5000/accounts")
print("2. Click 'Add Account'")
print("3. Fill in:")
print("   - Account Name: Your account name")
print("   - Organization ID: " + org_id)
print("   - Cookies: Copy the COOKIES JSON above")
print("   - Headers: Copy the HEADERS JSON above")
print("4. Click 'Save Account'")
print("=" * 50) 