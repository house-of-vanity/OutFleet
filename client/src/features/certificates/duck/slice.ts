import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { CertificateDTO } from './dto';

export interface CertificatesState {
  loading: boolean;
  certificates: CertificateDTO[]
  error: null | string;
}

const initialState: CertificatesState = {
  loading: false,
  certificates: [],
  error: null,
};

export const certificateSlice = createSlice({
  name: 'certificates',
  initialState,
  reducers: {
    setLoading: (state, action: PayloadAction<boolean>) => {
        state.loading = action.payload
    },
    setUsers: (state, action: PayloadAction<CertificateDTO[]>) => {
        state.certificates = action.payload
    },
    setError: (state, action: PayloadAction<string>) => {
        state.error = action.payload
    }
  },
});

