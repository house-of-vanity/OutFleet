import { certificateSlice } from './slice';
import { getCertificates } from './api';
import { createAsyncThunk } from '@reduxjs/toolkit';
import { getCertificatesState } from './selectors';
import type { RootState } from '../../../store';

const PREFFIX = 'certificates'

export const fetchCertificates = createAsyncThunk(
  `${PREFFIX}/fetchAll`,
  async (_, { dispatch, getState }) => {
    const { loading } = getCertificatesState(getState() as RootState);
    try {
      if (loading) {
        return;
      }

      dispatch(certificateSlice.actions.setLoading(true));
      const response = await getCertificates().then(({ data }) => data);
      dispatch(certificateSlice.actions.setUsers(response));

    } catch (e) {
      const message =
        e instanceof Error ? e.message : `Unknown error in ${PREFFIX}/fetchAll`;
      dispatch(certificateSlice.actions.setError(message));
    } finally {
      dispatch(certificateSlice.actions.setLoading(false));
    }
  },
);
