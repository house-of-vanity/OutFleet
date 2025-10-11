import { serversSlice } from './slice';
import { createServer, deleteServer, getServers, patchServer } from './api';
import { createAsyncThunk } from '@reduxjs/toolkit';
import { getServersState } from './selectors';
import type { RootState } from '../../../store';
import type { CreateServerDTO } from './dto';
import { appNotificator } from '../../../utils/notification/app-notificator';

const PREFFIX = 'servers';

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

export const createServerAction = createAsyncThunk(
  `${PREFFIX}/createServer`,
  async (params: CreateServerDTO, { dispatch }) => {
    try {
      await createServer(params);
      dispatch(fetchServers());
    } catch (e) {
      appNotificator.add({
        message:
          e instanceof Error
            ? e.message
            : `Unknown error in ${PREFFIX}/createServer`,
        type: 'error',
      });
    }
  },
);

export const deleteServerAction = createAsyncThunk(
  `${PREFFIX}/deleteServer`,
  async (id: string, { dispatch }) => {
    try {
      await deleteServer(id);
      appNotificator.add({
        message: 'Server deleted',
        type: 'success',
      });
      dispatch(fetchServers());
    } catch (e) {
      appNotificator.add({
        type: 'error',
        message:
          e instanceof Error
            ? `Delete error: ${e.message}`
            : `Unknown error in ${PREFFIX}/deleteServer`,
      });
    }
  },
);

export const updateServer = createAsyncThunk(
  `${PREFFIX}/updateServer`,
  async (
    params: {
      id: string;
      server: CreateServerDTO;
    },
    { dispatch },
  ) => {
    try {
      await patchServer(params.id, params.server);
      dispatch(fetchServers());
      appNotificator.add({
        message: 'Server updated',
        type: 'success',
      });
    } catch (e) {
      appNotificator.add({
        type: 'error',
        message:
          e instanceof Error
            ? `Error updating: ${e.message}`
            : `Unknown error in ${PREFFIX}/deleteServer`,
      });
    }
  },
);
