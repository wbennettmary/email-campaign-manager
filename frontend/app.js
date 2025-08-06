/**
 * Professional Email Campaign Manager - Frontend JavaScript
 * Modern ES6+ JavaScript with WebSocket real-time updates
 */

class CampaignManager {
    constructor() {
        this.baseURL = window.location.origin;
        this.apiURL = `${this.baseURL}/api`;
        this.wsURL = `ws://${window.location.host}/ws`;
        this.authToken = localStorage.getItem('authToken');
        this.socket = null;
        this.clientId = Math.random().toString(36).substr(2, 9);
        
        this.init();
    }

    async init() {
        this.setupEventListeners();
        
        if (this.authToken) {
            await this.loadDashboard();
            this.connectWebSocket();
        } else {
            this.showLogin();
        }
    }

    setupEventListeners() {
        // Navigation
        document.getElementById('logout-btn')?.addEventListener('click', () => this.logout());
        document.getElementById('refresh-campaigns')?.addEventListener('click', () => this.loadCampaigns());
        
        // Quick actions
        document.getElementById('new-campaign-btn')?.addEventListener('click', () => this.showNewCampaignForm());
        document.getElementById('upload-list-btn')?.addEventListener('click', () => this.showUploadForm());
        document.getElementById('add-account-btn')?.addEventListener('click', () => this.showAddAccountForm());
        
        // Filters
        document.getElementById('status-filter')?.addEventListener('change', (e) => {
            this.loadCampaigns(e.target.value);
        });
        
        // Modal
        document.getElementById('close-modal')?.addEventListener('click', () => this.hideModal());
        document.getElementById('campaign-modal')?.addEventListener('click', (e) => {
            if (e.target.id === 'campaign-modal') this.hideModal();
        });
    }

    // API Methods
    async apiRequest(endpoint, options = {}) {
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...(this.authToken && { 'Authorization': `Bearer ${this.authToken}` })
            },
            ...options
        };

        try {
            const response = await fetch(`${this.apiURL}${endpoint}`, config);
            
            if (!response.ok) {
                if (response.status === 401) {
                    this.logout();
                    return null;
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            console.error('API Request failed:', error);
            this.showToast(`Error: ${error.message}`, 'error');
            return null;
        }
    }

    // Authentication
    async login(username, password) {
        const response = await this.apiRequest('/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });

        if (response?.access_token) {
            this.authToken = response.access_token;
            localStorage.setItem('authToken', this.authToken);
            localStorage.setItem('user', JSON.stringify(response.user));
            
            await this.loadDashboard();
            this.connectWebSocket();
            this.showToast('Login successful!', 'success');
        }
    }

    logout() {
        this.authToken = null;
        localStorage.removeItem('authToken');
        localStorage.removeItem('user');
        
        if (this.socket) {
            this.socket.close();
        }
        
        this.showLogin();
        this.showToast('Logged out successfully', 'info');
    }

    // Dashboard
    async loadDashboard() {
        document.body.innerHTML = `
            ${document.body.innerHTML}
        `;
        
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        document.getElementById('username').textContent = user.username || 'User';
        
        await this.loadStats();
        await this.loadCampaigns();
        
        // Auto-refresh stats every 30 seconds
        setInterval(() => this.loadStats(), 30000);
    }

    async loadStats() {
        const stats = await this.apiRequest('/stats');
        if (stats) {
            document.getElementById('total-campaigns').textContent = stats.total_campaigns || 0;
            document.getElementById('active-campaigns').textContent = stats.active_campaigns || 0;
            document.getElementById('total-sent').textContent = (stats.total_sent || 0).toLocaleString();
            document.getElementById('success-rate').textContent = `${stats.delivery_rate || 0}%`;
        }
    }

    async loadCampaigns(statusFilter = '') {
        const url = statusFilter ? `/campaigns?status=${statusFilter}` : '/campaigns';
        const campaigns = await this.apiRequest(url);
        
        if (campaigns) {
            this.renderCampaigns(campaigns);
        }
    }

    renderCampaigns(campaigns) {
        const grid = document.getElementById('campaigns-grid');
        const noCampaigns = document.getElementById('no-campaigns');
        
        if (!campaigns || campaigns.length === 0) {
            grid.classList.add('hidden');
            noCampaigns.classList.remove('hidden');
            return;
        }
        
        noCampaigns.classList.add('hidden');
        grid.classList.remove('hidden');
        
        grid.innerHTML = campaigns.map(campaign => this.createCampaignCard(campaign)).join('');
        
        // Add event listeners to campaign cards
        campaigns.forEach(campaign => {
            const card = document.getElementById(`campaign-${campaign.id}`);
            
            // Start/Pause button
            const actionBtn = card.querySelector('.action-btn');
            actionBtn?.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleCampaign(campaign.id, campaign.status);
            });
            
            // Delete button
            const deleteBtn = card.querySelector('.delete-btn');
            deleteBtn?.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteCampaign(campaign.id);
            });
            
            // Card click for details
            card.addEventListener('click', () => this.showCampaignDetails(campaign.id));
        });
    }

    createCampaignCard(campaign) {
        const statusClass = `status-${campaign.status}`;
        const statusIcon = this.getStatusIcon(campaign.status);
        const progressPercent = campaign.total_recipients > 0 
            ? Math.round((campaign.total_sent / campaign.total_recipients) * 100) 
            : 0;
        
        return `
            <div id="campaign-${campaign.id}" class="campaign-card bg-white rounded-xl shadow-lg p-6 cursor-pointer border-l-4 border-blue-500">
                <div class="flex items-center justify-between mb-4">
                    <h3 class="text-lg font-bold text-gray-900 truncate">${this.escapeHtml(campaign.name)}</h3>
                    <span class="px-3 py-1 rounded-full text-white text-xs font-medium ${statusClass}">
                        <i class="${statusIcon} mr-1"></i>
                        ${campaign.status.toUpperCase()}
                    </span>
                </div>
                
                <p class="text-gray-600 text-sm mb-4 truncate">${this.escapeHtml(campaign.subject)}</p>
                
                <div class="space-y-2 mb-4">
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-500">Recipients:</span>
                        <span class="font-medium">${campaign.total_recipients.toLocaleString()}</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-500">Sent:</span>
                        <span class="font-medium text-green-600">${campaign.total_sent.toLocaleString()}</span>
                    </div>
                    <div class="flex justify-between text-sm">
                        <span class="text-gray-500">Failed:</span>
                        <span class="font-medium text-red-600">${campaign.total_failed.toLocaleString()}</span>
                    </div>
                </div>
                
                <!-- Progress Bar -->
                <div class="mb-4">
                    <div class="flex justify-between text-xs text-gray-500 mb-1">
                        <span>Progress</span>
                        <span>${progressPercent}%</span>
                    </div>
                    <div class="w-full bg-gray-200 rounded-full h-2">
                        <div class="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                             style="width: ${progressPercent}%"></div>
                    </div>
                </div>
                
                <div class="flex space-x-2">
                    <button class="action-btn flex-1 px-4 py-2 rounded-lg transition text-sm font-medium ${this.getActionButtonClass(campaign.status)}">
                        <i class="${this.getActionIcon(campaign.status)} mr-1"></i>
                        ${this.getActionText(campaign.status)}
                    </button>
                    <button class="delete-btn bg-red-500 hover:bg-red-600 text-white px-3 py-2 rounded-lg transition">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
                
                <div class="mt-3 text-xs text-gray-500">
                    Created: ${new Date(campaign.created_at).toLocaleDateString()}
                </div>
            </div>
        `;
    }

    getStatusIcon(status) {
        const icons = {
            'running': 'fas fa-play',
            'paused': 'fas fa-pause',
            'completed': 'fas fa-check',
            'failed': 'fas fa-exclamation-triangle',
            'draft': 'fas fa-edit',
            'ready': 'fas fa-clock'
        };
        return icons[status] || 'fas fa-question';
    }

    getActionButtonClass(status) {
        if (status === 'running') {
            return 'bg-yellow-500 hover:bg-yellow-600 text-white';
        } else if (status === 'paused' || status === 'ready') {
            return 'bg-green-500 hover:bg-green-600 text-white';
        } else {
            return 'bg-gray-400 text-white cursor-not-allowed';
        }
    }

    getActionIcon(status) {
        if (status === 'running') {
            return 'fas fa-pause';
        } else if (status === 'paused' || status === 'ready') {
            return 'fas fa-play';
        } else {
            return 'fas fa-ban';
        }
    }

    getActionText(status) {
        if (status === 'running') {
            return 'Pause';
        } else if (status === 'paused') {
            return 'Resume';
        } else if (status === 'ready') {
            return 'Start';
        } else {
            return 'Unavailable';
        }
    }

    // Campaign Actions
    async toggleCampaign(campaignId, currentStatus) {
        let endpoint, action;
        
        if (currentStatus === 'running') {
            endpoint = `/campaigns/${campaignId}/pause`;
            action = 'pause';
        } else if (currentStatus === 'paused' || currentStatus === 'ready') {
            endpoint = `/campaigns/${campaignId}/start`;
            action = 'start';
        } else {
            this.showToast('Cannot perform action on this campaign', 'warning');
            return;
        }
        
        const response = await this.apiRequest(endpoint, { method: 'POST' });
        if (response) {
            this.showToast(`Campaign ${action}ed successfully!`, 'success');
            await this.loadCampaigns();
        }
    }

    async deleteCampaign(campaignId) {
        if (!confirm('Are you sure you want to delete this campaign? This action cannot be undone.')) {
            return;
        }
        
        const response = await this.apiRequest(`/campaigns/${campaignId}`, { method: 'DELETE' });
        if (response) {
            this.showToast('Campaign deleted successfully!', 'success');
            await this.loadCampaigns();
            await this.loadStats();
        }
    }

    async showCampaignDetails(campaignId) {
        const campaign = await this.apiRequest(`/campaigns/${campaignId}`);
        if (campaign) {
            this.showModal('Campaign Details', this.createCampaignDetailsContent(campaign));
        }
    }

    createCampaignDetailsContent(campaign) {
        return `
            <div class="space-y-4">
                <div>
                    <h4 class="font-medium text-gray-900">Campaign Name</h4>
                    <p class="text-gray-600">${this.escapeHtml(campaign.name)}</p>
                </div>
                <div>
                    <h4 class="font-medium text-gray-900">Subject</h4>
                    <p class="text-gray-600">${this.escapeHtml(campaign.subject)}</p>
                </div>
                <div>
                    <h4 class="font-medium text-gray-900">Status</h4>
                    <span class="px-2 py-1 rounded text-xs font-medium ${this.getStatusClass(campaign.status)}">
                        ${campaign.status.toUpperCase()}
                    </span>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <h4 class="font-medium text-gray-900">Recipients</h4>
                        <p class="text-2xl font-bold text-blue-600">${campaign.total_recipients.toLocaleString()}</p>
                    </div>
                    <div>
                        <h4 class="font-medium text-gray-900">Sent</h4>
                        <p class="text-2xl font-bold text-green-600">${campaign.total_sent.toLocaleString()}</p>
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <h4 class="font-medium text-gray-900">Failed</h4>
                        <p class="text-2xl font-bold text-red-600">${campaign.total_failed.toLocaleString()}</p>
                    </div>
                    <div>
                        <h4 class="font-medium text-gray-900">Success Rate</h4>
                        <p class="text-2xl font-bold text-purple-600">${this.calculateSuccessRate(campaign)}%</p>
                    </div>
                </div>
                ${campaign.started_at ? `
                    <div>
                        <h4 class="font-medium text-gray-900">Started</h4>
                        <p class="text-gray-600">${new Date(campaign.started_at).toLocaleString()}</p>
                    </div>
                ` : ''}
                ${campaign.completed_at ? `
                    <div>
                        <h4 class="font-medium text-gray-900">Completed</h4>
                        <p class="text-gray-600">${new Date(campaign.completed_at).toLocaleString()}</p>
                    </div>
                ` : ''}
            </div>
        `;
    }

    calculateSuccessRate(campaign) {
        const total = campaign.total_sent + campaign.total_failed;
        return total > 0 ? Math.round((campaign.total_sent / total) * 100) : 0;
    }

    getStatusClass(status) {
        const classes = {
            'running': 'bg-green-100 text-green-800',
            'paused': 'bg-yellow-100 text-yellow-800',
            'completed': 'bg-blue-100 text-blue-800',
            'failed': 'bg-red-100 text-red-800',
            'draft': 'bg-gray-100 text-gray-800',
            'ready': 'bg-purple-100 text-purple-800'
        };
        return classes[status] || 'bg-gray-100 text-gray-800';
    }

    // WebSocket Connection
    connectWebSocket() {
        try {
            this.socket = new WebSocket(`${this.wsURL}/${this.clientId}`);
            
            this.socket.onopen = () => {
                console.log('WebSocket connected');
                this.updateConnectionStatus('Connected', 'bg-green-500');
            };
            
            this.socket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.socket.onclose = () => {
                console.log('WebSocket disconnected');
                this.updateConnectionStatus('Disconnected', 'bg-red-500');
                
                // Attempt to reconnect after 5 seconds
                setTimeout(() => this.connectWebSocket(), 5000);
            };
            
            this.socket.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateConnectionStatus('Error', 'bg-red-500');
            };
            
        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
            this.updateConnectionStatus('Failed to connect', 'bg-red-500');
        }
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'campaign_started':
            case 'campaign_paused':
            case 'campaign_completed':
            case 'campaign_failed':
                this.loadCampaigns();
                this.loadStats();
                this.showToast(`Campaign ${data.type.split('_')[1]}!`, 'info');
                break;
                
            case 'campaign_progress':
                this.updateCampaignProgress(data.campaign_id, data);
                break;
                
            case 'campaign_deleted':
                this.loadCampaigns();
                this.loadStats();
                break;
                
            default:
                console.log('Unhandled WebSocket message:', data);
        }
    }

    updateCampaignProgress(campaignId, progress) {
        const card = document.getElementById(`campaign-${campaignId}`);
        if (card) {
            // Update sent count
            const sentElement = card.querySelector('.text-green-600');
            if (sentElement) {
                sentElement.textContent = progress.total_sent.toLocaleString();
            }
            
            // Update failed count
            const failedElement = card.querySelector('.text-red-600');
            if (failedElement) {
                failedElement.textContent = progress.total_failed.toLocaleString();
            }
            
            // Update progress bar
            const progressBar = card.querySelector('.bg-blue-600');
            const progressText = card.querySelector('.text-xs.text-gray-500 span:last-child');
            if (progressBar && progressText && progress.progress_percent) {
                progressBar.style.width = `${progress.progress_percent}%`;
                progressText.textContent = `${progress.progress_percent}%`;
            }
        }
    }

    updateConnectionStatus(status, className) {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg text-white text-sm ${className}`;
            statusElement.innerHTML = `
                <i class="fas fa-circle mr-2"></i>
                <span>${status}</span>
            `;
        }
    }

    // UI Helper Methods
    showModal(title, content) {
        const modal = document.getElementById('campaign-modal');
        const modalContent = document.getElementById('modal-content');
        
        modal.querySelector('h3').textContent = title;
        modalContent.innerHTML = content;
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }

    hideModal() {
        const modal = document.getElementById('campaign-modal');
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        
        const typeClasses = {
            'success': 'bg-green-500',
            'error': 'bg-red-500',
            'warning': 'bg-yellow-500',
            'info': 'bg-blue-500'
        };
        
        const typeIcons = {
            'success': 'fas fa-check-circle',
            'error': 'fas fa-exclamation-circle',
            'warning': 'fas fa-exclamation-triangle',
            'info': 'fas fa-info-circle'
        };
        
        toast.className = `${typeClasses[type]} text-white px-6 py-3 rounded-lg shadow-lg flex items-center space-x-2 transform transition-all duration-300 translate-x-full`;
        toast.innerHTML = `
            <i class="${typeIcons[type]}"></i>
            <span>${this.escapeHtml(message)}</span>
            <button class="ml-4 text-white hover:text-gray-200" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        container.appendChild(toast);
        
        // Animate in
        setTimeout(() => {
            toast.classList.remove('translate-x-full');
        }, 100);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            toast.classList.add('translate-x-full');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    showLogin() {
        document.body.innerHTML = `
            <div class="min-h-screen gradient-bg flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
                <div class="max-w-md w-full space-y-8">
                    <div class="text-center">
                        <i class="fas fa-envelope text-white text-6xl mb-4"></i>
                        <h2 class="text-4xl font-bold text-white mb-2">Campaign Manager Pro</h2>
                        <p class="text-white opacity-90">Professional Email Campaign Management</p>
                    </div>
                    
                    <div class="glass-effect rounded-xl p-8">
                        <form id="login-form" class="space-y-6">
                            <div>
                                <label for="username" class="sr-only">Username</label>
                                <input id="username" name="username" type="text" required 
                                       class="w-full px-3 py-3 border border-gray-300 rounded-lg placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                       placeholder="Username">
                            </div>
                            <div>
                                <label for="password" class="sr-only">Password</label>
                                <input id="password" name="password" type="password" required 
                                       class="w-full px-3 py-3 border border-gray-300 rounded-lg placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                       placeholder="Password">
                            </div>
                            <div>
                                <button type="submit" 
                                        class="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-lg text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition">
                                    <i class="fas fa-sign-in-alt mr-2"></i>
                                    Sign in
                                </button>
                            </div>
                        </form>
                        
                        <div class="mt-6 text-center">
                            <p class="text-white text-sm">
                                Demo: admin / admin123
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Add login form event listener
        document.getElementById('login-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            await this.login(username, password);
        });
    }

    // Placeholder methods for forms
    showNewCampaignForm() {
        this.showToast('Campaign creation form coming soon!', 'info');
    }

    showUploadForm() {
        this.showToast('Email list upload coming soon!', 'info');
    }

    showAddAccountForm() {
        this.showToast('Add account form coming soon!', 'info');
    }

    // Utility Methods
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, (m) => map[m]);
    }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    window.campaignManager = new CampaignManager();
});

// Global error handler
window.addEventListener('error', (event) => {
    console.error('Global error:', event.error);
    if (window.campaignManager) {
        window.campaignManager.showToast('An unexpected error occurred', 'error');
    }
});