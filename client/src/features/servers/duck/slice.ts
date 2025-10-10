import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { ServerDTO } from './dto';

export interface ServersState {
  loading: boolean;
  servers: ServerDTO[];
  error: null | string;
}

const initialState: ServersState = {
  loading: false,
  servers: [],
  error: null,
};

export const serversSlice = createSlice({
  name: 'servers',
  initialState,
  reducers: {
    setLoading: (state, action: PayloadAction<boolean>) => {
        state.loading = action.payload
    },
    setServers: (state, action: PayloadAction<ServerDTO[]>) => {
        state.servers = action.payload
    },
    setError: (state, action: PayloadAction<string>) => {
        state.error = action.payload
    }
  },
});

