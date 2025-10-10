import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { TemplateDTO } from './dto';

export interface TemplateState {
  loading: boolean;
  templates: TemplateDTO[];
  error: null | string;
}

const initialState: TemplateState = {
  loading: false,
  templates: [],
  error: null,
};

export const templatesSlice = createSlice({
  name: 'templates',
  initialState,
  reducers: {
    setLoading: (state, action: PayloadAction<boolean>) => {
        state.loading = action.payload
    },
    setTemplates: (state, action: PayloadAction<TemplateDTO[]>) => {
        state.templates = action.payload
    },
    setError: (state, action: PayloadAction<string>) => {
        state.error = action.payload
    }
  },
});

