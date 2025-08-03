# 🕐 Campaign Automation System Guide

## Overview

The Campaign Automation System allows you to schedule campaigns to run automatically at specific times. This feature enables you to:

- ✅ **Schedule campaigns** to run once, daily, weekly, monthly, or at custom intervals
- ✅ **Automate email delivery** without manual intervention
- ✅ **Manage multiple schedules** with a user-friendly interface
- ✅ **Monitor execution status** and get notifications
- ✅ **Execute campaigns immediately** when needed

## 🚀 Getting Started

### Accessing the Automation Dashboard

1. Navigate to **Automation** in the sidebar menu
2. You'll see the automation dashboard with statistics and scheduled campaigns

### Creating Your First Schedule

1. Click **"Schedule Campaign"** button
2. Select a campaign from the dropdown (only "ready" campaigns are available)
3. Choose the schedule type:
   - **Once**: Run once at the specified time
   - **Daily**: Run every day at the same time
   - **Weekly**: Run every week on the same day and time
   - **Monthly**: Run every month on the same date and time
   - **Custom**: Run at custom intervals (in minutes)
4. Set the date and time for the first execution
5. Enable/disable the schedule
6. Click **"Schedule Campaign"**

## 📊 Dashboard Features

### Statistics Cards

- **Total Schedules**: Number of all scheduled campaigns
- **Active Schedules**: Number of enabled schedules
- **Completed Today**: Number of campaigns executed today
- **Next Execution**: Time until the next scheduled campaign runs

### Schedules Table

The table shows all your scheduled campaigns with:

- **Campaign Name & Subject**: Which campaign is scheduled
- **Schedule Type**: How often it runs
- **Next Run**: When it will execute next
- **Last Run**: When it was last executed
- **Total Runs**: How many times it has been executed
- **Status**: Current status (Pending, Completed, Failed, Disabled)

### Action Buttons

For each schedule, you can:

- **Edit** (✏️): Modify the schedule settings
- **Toggle** (▶️/⏸️): Enable or disable the schedule
- **Execute Now** (⚡): Run the campaign immediately
- **Delete** (🗑️): Remove the schedule

## ⚙️ Schedule Types Explained

### Once
- Runs one time at the specified date and time
- Automatically disabled after execution
- Perfect for one-time campaigns

### Daily
- Runs every day at the same time
- Continues indefinitely until disabled
- Ideal for daily newsletters or updates

### Weekly
- Runs every week on the same day and time
- Continues indefinitely until disabled
- Great for weekly reports or newsletters

### Monthly
- Runs every month on the same date and time
- Continues indefinitely until disabled
- Perfect for monthly summaries or announcements

### Custom Interval
- Runs at specified intervals (in minutes)
- Continues indefinitely until disabled
- Useful for frequent updates or testing

## 🔧 Advanced Features

### Immediate Execution
- Click the **"Execute Now"** button to run any scheduled campaign immediately
- Useful for testing or urgent campaigns
- Doesn't affect the regular schedule

### Schedule Management
- **Edit schedules** to change timing or frequency
- **Enable/disable** schedules without deleting them
- **Delete schedules** to remove them permanently

### Notifications
- Get notifications when campaigns are scheduled successfully
- Receive alerts when campaigns complete or fail
- Monitor execution status in real-time

## 📋 Best Practices

### Scheduling Tips
1. **Test campaigns** before scheduling them
2. **Use appropriate intervals** for your audience
3. **Monitor delivery rates** and adjust timing if needed
4. **Consider time zones** when scheduling

### Campaign Preparation
1. Ensure campaigns are in **"ready"** status
2. Verify account credentials are valid
3. Check data lists are properly configured
4. Test with small batches first

### Monitoring
1. Check the automation dashboard regularly
2. Monitor execution logs for any issues
3. Review bounce and delivery reports
4. Adjust schedules based on performance

## 🛠️ Technical Details

### Background Processing
- The automation system runs in the background
- Checks for scheduled campaigns every 60 seconds
- Automatically executes campaigns when their time comes
- Updates schedule status after execution

### Data Storage
- Schedules are stored in `scheduled_campaigns.json`
- Each schedule includes:
  - Campaign ID and details
  - Schedule type and timing
  - Execution history
  - Status information

### Error Handling
- Failed executions are logged
- Notifications are sent for failures
- Schedules remain active unless manually disabled
- Retry logic for temporary failures

## 🔍 Troubleshooting

### Common Issues

**Campaign not executing:**
- Check if the schedule is enabled
- Verify the campaign status is "ready"
- Ensure account credentials are valid
- Check execution logs for errors

**Schedule not appearing:**
- Refresh the automation dashboard
- Check if the campaign exists and is ready
- Verify you have proper permissions

**Execution failures:**
- Check account authentication
- Verify data lists are accessible
- Review rate limiting settings
- Check system logs for details

### Getting Help
- Check the execution logs in the campaign logs page
- Review notifications for error messages
- Verify account and campaign settings
- Contact support if issues persist

## 🎯 Use Cases

### Marketing Campaigns
- Schedule promotional emails for optimal times
- Automate follow-up sequences
- Send regular newsletters

### Business Communications
- Automated weekly reports
- Monthly updates to stakeholders
- Regular announcements

### Testing and Development
- Test campaigns at specific times
- Validate delivery systems
- Monitor performance over time

---

## 🚀 Ready to Automate?

The automation system is now fully integrated into your email campaign manager. Start by creating your first scheduled campaign and watch your emails deliver automatically!

For support or questions, check the logs and notifications, or refer to this guide for troubleshooting steps. 