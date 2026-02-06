/**
 * OmniBar API Service
 * 
 * Handles communication with the OmniBar backend endpoints.
 */

import apiClient from './client';

export interface OmniBarMessage {
  role: 'user' | 'assistant';
  content: string;
  intent?: string;
  data?: Record<string, any>;
  suggestions?: string[];
  timestamp?: string;
}

export interface OmniBarResponse {
  success: boolean;
  message: string;
  intent: string;
  data?: Record<string, any>;
  suggestions?: string[];
  confidence: number;
}

export interface SuggestionResponse {
  suggestions: string[];
}

export const omnibarApi = {
  /**
   * Process a natural language command
   */
  process: async (
    message: string,
    history?: OmniBarMessage[]
  ): Promise<OmniBarResponse> => {
    const response = await apiClient.post<OmniBarResponse>('/api/omnibar/process', {
      message,
      history: history?.map(h => ({ role: h.role, content: h.content })),
    }, {
      timeout: 30000, // 30s timeout for AI processing
    });
    return response.data;
  },

  /**
   * Get autocomplete suggestions
   */
  suggest: async (query: string): Promise<string[]> => {
    const response = await apiClient.get<SuggestionResponse>('/api/omnibar/suggest', {
      params: { q: query },
    });
    return response.data.suggestions;
  },
};

export default omnibarApi;
