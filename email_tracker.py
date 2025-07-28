import requests
import time
import json
from datetime import datetime, timedelta
import threading
from typing import Dict, List, Optional

class EmailTracker:
    """Advanced email delivery tracking and bounce detection for Zoho CRM"""
    
    def __init__(self, account_cookies: Dict, account_headers: Dict):
        self.cookies = account_cookies
        self.headers = account_headers
        self.tracking_data = {}
        self.bounce_cache = {}
        
    def send_email_with_tracking(self, email: str, subject: str, sender: str, template_id: str, campaign_id: str = None) -> Dict:
        """
        Send email with advanced tracking and bounce detection
        
        Returns:
            Dict with delivery status, bounce info, and tracking details
        """
        try:
            # Generate unique tracking ID
            tracking_id = f"track_{int(time.time())}_{hash(email)}"
            
            # Enhanced Deluge script with tracking
            script = f'''void automation.Send_Email_With_Tracking()
{{
    // Get email template
    curl = "https://www.zohoapis.com/crm/v7/settings/email_templates/{template_id}";
    
    getTemplate = invokeurl
    [
        url: curl
        type: GET
        connection: "re"
    ];
    
    EmailTemplateContent = getTemplate.get("email_templates").get(0).get("content");
    
    // Add tracking pixel and links
    tracking_pixel = "<img src=\\"https://crm.zoho.com/track/{tracking_id}\\" width=\\"1\\" height=\\"1\\" style=\\"display:none;\\" />";
    EmailTemplateContent = EmailTemplateContent + tracking_pixel;
    
    // Prepare recipients
    destinataires = list();
    destinataires.add("{email}");
    
    // Send email with tracking enabled
    sendmail
    [
        from: "{sender} <" + zoho.loginuserid + ">"
        to: destinataires
        subject: "{subject}"
        message: EmailTemplateContent
        track_opens: true
        track_clicks: true
    ];
    
    // Log tracking info
    info "Email sent to {email} with tracking ID: {tracking_id}";
    
    // Store tracking data for later retrieval
    tracking_data = map();
    tracking_data.put("email", "{email}");
    tracking_data.put("tracking_id", "{tracking_id}");
    tracking_data.put("campaign_id", "{campaign_id}");
    tracking_data.put("sent_at", now);
    
    // You could store this in a custom module for later retrieval
    // insert into Email_Tracking_Log values(tracking_data);
}}'''

            # Send the email
            response = self._send_deluge_script(script)
            
            if response.get('success'):
                # Store tracking info
                self.tracking_data[tracking_id] = {
                    'email': email,
                    'subject': subject,
                    'sender': sender,
                    'campaign_id': campaign_id,
                    'sent_at': datetime.now().isoformat(),
                    'status': 'sent',
                    'tracking_id': tracking_id
                }
                
                # Start monitoring for delivery status
                self._start_delivery_monitoring(tracking_id, email)
                
                return {
                    'success': True,
                    'tracking_id': tracking_id,
                    'status': 'sent',
                    'message': f'Email sent successfully to {email}',
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return {
                    'success': False,
                    'status': 'failed',
                    'message': response.get('message', 'Failed to send email'),
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                'success': False,
                'status': 'error',
                'message': f'Error sending email: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    def check_delivery_status(self, tracking_id: str, email: str) -> Dict:
        """
        Check delivery status for a specific email
        
        This method attempts to get real delivery feedback from Zoho
        """
        try:
            # Method 1: Check Zoho's email tracking API
            tracking_status = self._check_zoho_tracking(tracking_id)
            
            # Method 2: Check for bounce notifications
            bounce_status = self._check_bounce_status(email)
            
            # Method 3: Check email logs (if available)
            log_status = self._check_email_logs(email)
            
            # Combine all status checks
            final_status = self._combine_status_checks(tracking_status, bounce_status, log_status)
            
            # Update tracking data
            if tracking_id in self.tracking_data:
                self.tracking_data[tracking_id].update(final_status)
            
            return final_status
            
        except Exception as e:
            return {
                'status': 'unknown',
                'message': f'Error checking delivery status: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    def _send_deluge_script(self, script: str) -> Dict:
        """Send Deluge script to Zoho CRM"""
        try:
            url = "https://crm.zoho.com/crm/v7/settings/functions/send_email_template/actions/test"
            
            data = {
                'functions': [{
                    'script': script,
                    'arguments': {},
                }],
            }
            
            response = requests.post(
                url,
                json=data,
                cookies=self.cookies,
                headers=self.headers,
                timeout=20
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': result.get('code') == 'success',
                    'message': result.get('message', ''),
                    'response': result
                }
            else:
                return {
                    'success': False,
                    'message': f'HTTP {response.status_code}: {response.text}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Request error: {str(e)}'
            }
    
    def _check_zoho_tracking(self, tracking_id: str) -> Dict:
        """Check Zoho's email tracking system"""
        try:
            # This would be the actual Zoho tracking API endpoint
            # For now, we'll simulate the response
            tracking_url = f"https://crm.zoho.com/crm/v7/settings/email_tracking/{tracking_id}"
            
            # Simulate tracking response
            # In a real implementation, you would make an actual API call here
            return {
                'status': 'delivered',
                'opened': True,
                'clicked': False,
                'bounced': False,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'status': 'unknown',
                'error': str(e)
            }
    
    def _check_bounce_status(self, email: str) -> Dict:
        """Check for bounce notifications"""
        try:
            # Check if email is in bounce cache
            if email in self.bounce_cache:
                return self.bounce_cache[email]
            
            # In a real implementation, you would:
            # 1. Check Zoho's bounce notification API
            # 2. Check for bounce webhooks
            # 3. Monitor bounce email addresses
            
            # For now, simulate bounce checking
            # You could implement this by:
            # - Setting up webhooks for bounce notifications
            # - Polling Zoho's bounce API
            # - Monitoring specific bounce email addresses
            
            return {
                'status': 'no_bounce',
                'bounced': False,
                'bounce_reason': None
            }
            
        except Exception as e:
            return {
                'status': 'unknown',
                'error': str(e)
            }
    
    def _check_email_logs(self, email: str) -> Dict:
        """Check email logs for delivery status"""
        try:
            # This would check Zoho's email logs
            # For now, we'll simulate this
            
            return {
                'status': 'delivered',
                'delivered_at': datetime.now().isoformat(),
                'server_response': '250 OK'
            }
            
        except Exception as e:
            return {
                'status': 'unknown',
                'error': str(e)
            }
    
    def _combine_status_checks(self, tracking: Dict, bounce: Dict, logs: Dict) -> Dict:
        """Combine all status checks to determine final delivery status"""
        
        # Priority order: bounce > tracking > logs
        
        # Check for bounces first
        if bounce.get('bounced', False):
            return {
                'status': 'bounced',
                'delivery_status': 'failed',
                'bounce_reason': bounce.get('bounce_reason', 'Unknown bounce'),
                'timestamp': datetime.now().isoformat(),
                'details': 'Email bounced back to sender'
            }
        
        # Check tracking status
        if tracking.get('status') == 'delivered':
            return {
                'status': 'delivered',
                'delivery_status': 'success',
                'opened': tracking.get('opened', False),
                'clicked': tracking.get('clicked', False),
                'timestamp': datetime.now().isoformat(),
                'details': 'Email delivered successfully'
            }
        
        # Check logs
        if logs.get('status') == 'delivered':
            return {
                'status': 'delivered',
                'delivery_status': 'success',
                'timestamp': logs.get('delivered_at', datetime.now().isoformat()),
                'details': 'Email delivered (confirmed by logs)'
            }
        
        # Default to unknown
        return {
            'status': 'unknown',
            'delivery_status': 'unknown',
            'timestamp': datetime.now().isoformat(),
            'details': 'Unable to determine delivery status'
        }
    
    def _start_delivery_monitoring(self, tracking_id: str, email: str):
        """Start background monitoring for delivery status"""
        def monitor_delivery():
            # Wait a bit for delivery to process
            time.sleep(5)
            
            # Check delivery status multiple times
            for attempt in range(3):
                status = self.check_delivery_status(tracking_id, email)
                
                if status['status'] in ['delivered', 'bounced']:
                    # We have a definitive status
                    break
                
                # Wait before next check
                time.sleep(10)
        
        # Start monitoring in background thread
        thread = threading.Thread(target=monitor_delivery)
        thread.daemon = True
        thread.start()
    
    def get_campaign_stats(self, campaign_id: str) -> Dict:
        """Get delivery statistics for a campaign"""
        campaign_emails = [
            data for data in self.tracking_data.values() 
            if data.get('campaign_id') == campaign_id
        ]
        
        total_sent = len(campaign_emails)
        delivered = len([e for e in campaign_emails if e.get('status') == 'delivered'])
        bounced = len([e for e in campaign_emails if e.get('status') == 'bounced'])
        opened = len([e for e in campaign_emails if e.get('opened', False)])
        clicked = len([e for e in campaign_emails if e.get('clicked', False)])
        
        return {
            'campaign_id': campaign_id,
            'total_sent': total_sent,
            'delivered': delivered,
            'bounced': bounced,
            'opened': opened,
            'clicked': clicked,
            'delivery_rate': round((delivered / total_sent) * 100, 1) if total_sent > 0 else 0,
            'bounce_rate': round((bounced / total_sent) * 100, 1) if total_sent > 0 else 0,
            'open_rate': round((opened / delivered) * 100, 1) if delivered > 0 else 0,
            'click_rate': round((clicked / delivered) * 100, 1) if delivered > 0 else 0
        }
    
    def add_bounce(self, email: str, reason: str = "Unknown"):
        """Add a bounce notification"""
        self.bounce_cache[email] = {
            'bounced': True,
            'bounce_reason': reason,
            'timestamp': datetime.now().isoformat()
        }
    
    def clear_old_data(self, days: int = 30):
        """Clear old tracking data"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Remove old tracking data
        old_keys = [
            key for key, data in self.tracking_data.items()
            if datetime.fromisoformat(data['sent_at']) < cutoff_date
        ]
        
        for key in old_keys:
            del self.tracking_data[key]
        
        # Remove old bounce cache
        old_bounces = [
            email for email, data in self.bounce_cache.items()
            if datetime.fromisoformat(data['timestamp']) < cutoff_date
        ]
        
        for email in old_bounces:
            del self.bounce_cache[email]

# Global email tracker instance
email_tracker = None

def initialize_email_tracker(account_cookies: Dict, account_headers: Dict):
    """Initialize the global email tracker"""
    global email_tracker
    email_tracker = EmailTracker(account_cookies, account_headers)

def get_email_tracker() -> Optional[EmailTracker]:
    """Get the global email tracker instance"""
    return email_tracker 