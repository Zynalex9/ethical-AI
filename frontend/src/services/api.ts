import axios, { type AxiosInstance, type AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

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
    // Run selected validations in background
    runAll: async (data: {
        model_id: string;
        dataset_id: string;
        selected_validations?: string[];
        fairness_config: {
            sensitive_feature: string;
            target_column: string | null;
            selected_metrics?: string[];
            thresholds?: Record<string, number>;
        };
        transparency_config: {
            target_column: string | null;
            sample_size?: number;
        };
        privacy_config: {
            selected_checks?: string[];
            k_anonymity_k?: number;
            l_diversity_l?: number;
            quasi_identifiers?: string[];
            sensitive_attribute?: string;
        };
        requirement_ids?: string[];
    }) => {
        const response = await api.post('/validate/all', data);
        return response.data;
    },

    // Check task status
    getTaskStatus: async (taskId: string) => {
        const response = await api.get(`/validate/task/${taskId}`);
        return response.data;
    },

    // Get suite results
    getSuiteResults: async (suiteId: string) => {
        const response = await api.get(`/validate/suite/${suiteId}/results`);
        return response.data;
    },

    // Get detailed privacy validation results
    getPrivacyDetails: async (suiteId: string) => {
        const response = await api.get(`/validate/suite/${suiteId}/privacy-details`);
        return response.data;
    },

    // Get detailed transparency validation results
    getTransparencyDetails: async (suiteId: string) => {
        const response = await api.get(`/validate/suite/${suiteId}/transparency-details`);
        return response.data;
    },

    // Legacy endpoints (still work for individual validations)
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

    // Get validation history
    getHistory: async (projectId: string) => {
        const response = await api.get(`/validate/history/${projectId}`);
        return response.data;
    },

    getResults: async (runId: string) => {
        const response = await api.get(`/validate/${runId}/results`);
        return response.data;
    },
};

// Requirements API
export const requirementsApi = {
    listByProject: async (projectId: string) => {
        const response = await api.get(`/requirements/project/${projectId}`);
        return response.data;
    },

    create: async (projectId: string, data: {
        name: string;
        principle: string;
        description?: string;
        specification?: Record<string, any>;
        based_on_template_id?: string;
    }) => {
        const response = await api.post(`/requirements/project/${projectId}`, data);
        return response.data;
    },

    update: async (requirementId: string, data: {
        name?: string;
        principle?: string;
        description?: string;
        specification?: Record<string, any>;
        status?: string;
    }) => {
        const response = await api.put(`/requirements/${requirementId}`, data);
        return response.data;
    },

    delete: async (requirementId: string) => {
        const response = await api.delete(`/requirements/${requirementId}`);
        return response.data;
    },

    elicitFromDataset: async (data: { dataset_id: string; project_id: string }) => {
        const response = await api.post('/requirements/elicit-from-dataset', data);
        return response.data;
    },

    elicitFromModel: async (data: { model_id: string; dataset_id: string; project_id: string }) => {
        const response = await api.post('/requirements/elicit-from-model', data);
        return response.data;
    },

    acceptElicited: async (data: {
        project_id: string;
        name: string;
        principle: string;
        description?: string;
        specification?: Record<string, any>;
        elicitation_reason?: string;
        confidence_score?: number;
    }) => {
        const response = await api.post('/requirements/accept-elicited', data);
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

// Traceability API – Phase 3
export const traceabilityApi = {
    /** Full Requirement Traceability Matrix for a project */
    getMatrix: async (projectId: string) => {
        const response = await api.get(`/traceability/project/${projectId}/matrix`);
        return response.data;
    },

    /** Compliance history for a single requirement */
    getRequirementHistory: async (requirementId: string) => {
        const response = await api.get(`/traceability/requirement/${requirementId}/history`);
        return response.data;
    },

    /** Root-cause analysis for a validation run */
    getRootCause: async (validationId: string) => {
        const response = await api.get(`/traceability/validation/${validationId}/root-cause`);
        return response.data;
    },

    /** Impact of a dataset on requirements and validations */
    getDatasetImpact: async (datasetId: string) => {
        const response = await api.get(`/traceability/dataset/${datasetId}/impact`);
        return response.data;
    },
};

export default api;
