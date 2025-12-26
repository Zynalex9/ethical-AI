// API service for communicating with the backend

import axios, { type AxiosInstance, type AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// Create axios instance with default config
const api: AxiosInstance = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

// Request interceptor to add auth token
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// Response interceptor for error handling and token refresh
api.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const originalRequest = error.config;

        // If 401 and not already retrying, try to refresh token
        if (error.response?.status === 401 && originalRequest) {
            const refreshToken = localStorage.getItem('refresh_token');

            if (refreshToken) {
                try {
                    const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
                        refresh_token: refreshToken
                    });

                    const { access_token, refresh_token } = response.data;
                    localStorage.setItem('access_token', access_token);
                    localStorage.setItem('refresh_token', refresh_token);

                    // Retry original request
                    originalRequest.headers.Authorization = `Bearer ${access_token}`;
                    return api(originalRequest);
                } catch {
                    // Refresh failed, clear tokens and redirect to login
                    localStorage.removeItem('access_token');
                    localStorage.removeItem('refresh_token');
                    window.location.href = '/login';
                }
            }
        }

        return Promise.reject(error);
    }
);

// Auth API
export const authApi = {
    register: async (data: { email: string; password: string; name: string }) => {
        const response = await api.post('/auth/register', data);
        return response.data;
    },

    login: async (data: { email: string; password: string }) => {
        const response = await api.post('/auth/login', data);
        const { access_token, refresh_token } = response.data;
        localStorage.setItem('access_token', access_token);
        localStorage.setItem('refresh_token', refresh_token);
        return response.data;
    },

    logout: () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
    },

    getProfile: async () => {
        const response = await api.get('/auth/me');
        return response.data;
    },
};

// Projects API
export const projectsApi = {
    list: async () => {
        const response = await api.get('/projects');
        return response.data;
    },

    get: async (id: string) => {
        const response = await api.get(`/projects/${id}`);
        return response.data;
    },

    create: async (data: { name: string; description?: string }) => {
        const response = await api.post('/projects', data);
        return response.data;
    },

    update: async (id: string, data: { name?: string; description?: string }) => {
        const response = await api.put(`/projects/${id}`, data);
        return response.data;
    },

    delete: async (id: string) => {
        const response = await api.delete(`/projects/${id}`);
        return response.data;
    },
};

// Models API
export const modelsApi = {
    upload: async (projectId: string, file: File, name: string) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('name', name);
        formData.append('project_id', projectId);

        const response = await api.post('/models/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return response.data;
    },

    list: async (projectId: string) => {
        const response = await api.get(`/models/project/${projectId}`);
        return response.data;
    },

    delete: async (modelId: string) => {
        const response = await api.delete(`/models/${modelId}`);
        return response.data;
    },
};

// Datasets API
export const datasetsApi = {
    upload: async (projectId: string, file: File, name: string) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('name', name);
        formData.append('project_id', projectId);

        const response = await api.post('/datasets/upload', formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
        });
        return response.data;
    },

    list: async (projectId: string) => {
        const response = await api.get(`/datasets/project/${projectId}`);
        return response.data;
    },

    delete: async (datasetId: string) => {
        const response = await api.delete(`/datasets/${datasetId}`);
        return response.data;
    },
};

// Validation API
export const validationApi = {
    runFairness: async (modelId: string, datasetId: string, requirementId: string) => {
        const response = await api.post('/validate/fairness', {
            model_id: modelId,
            dataset_id: datasetId,
            requirement_id: requirementId,
        });
        return response.data;
    },

    runTransparency: async (modelId: string, datasetId: string) => {
        const response = await api.post('/validate/transparency', {
            model_id: modelId,
            dataset_id: datasetId,
        });
        return response.data;
    },

    runPrivacy: async (datasetId: string, requirements: object) => {
        const response = await api.post('/validate/privacy', {
            dataset_id: datasetId,
            requirements,
        });
        return response.data;
    },

    getResults: async (runId: string) => {
        const response = await api.get(`/validate/${runId}/results`);
        return response.data;
    },
};

// Templates API
export const templatesApi = {
    list: async () => {
        const response = await api.get('/templates');
        return response.data;
    },

    get: async (id: string) => {
        const response = await api.get(`/templates/${id}`);
        return response.data;
    },

    create: async (data: any) => {
        const response = await api.post('/templates', data);
        return response.data;
    },

    delete: async (id: string) => {
        const response = await api.delete(`/templates/${id}`);
        return response.data;
    },
};

// Audit API
export const auditApi = {
    list: async (params?: any) => {
        const response = await api.get('/audit', { params });
        return response.data;
    },

    getSummary: async () => {
        const response = await api.get('/audit/summary');
        return response.data;
    },

    get: async (id: string) => {
        const response = await api.get(`/audit/${id}`);
        return response.data;
    },
};

export default api;
