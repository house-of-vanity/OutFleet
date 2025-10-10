import { serversSlice } from './slice';
import { getServers } from './api';
import { createAsyncThunk } from '@reduxjs/toolkit';
import { getServersState } from './selectors';
import type { RootState } from '../../../store';

const PREFFIX = 'servers'

export const fetchServers = createAsyncThunk(
  `${PREFFIX}/fetchAll`,
  async (_, { dispatch, getState }) => {
    const { loading } = getServersState(getState() as RootState);
    try {
      if (loading) {
        return;
      }

      dispatch(serversSlice.actions.setLoading(true));
      const response = await getServers().then(({ data }) => data);
      dispatch(serversSlice.actions.setServers(response));

    } catch (e) {
      const message =
        e instanceof Error ? e.message : `Unknown error in ${PREFFIX}/fetchAll`;
      dispatch(serversSlice.actions.setError(message));
    } finally {
      dispatch(serversSlice.actions.setLoading(false));
    }
  },
);
