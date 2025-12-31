import { usersSlice } from './slice';
import { getUsers } from './api';
import { createAsyncThunk } from '@reduxjs/toolkit';
import { getUsersState } from './selectors';
import type { RootState } from '../../../store';

const PREFFIX = 'users'

export const fetchUsers = createAsyncThunk(
  `${PREFFIX}/fetchAll`,
  async (_, { dispatch, getState }) => {
    const { loading } = getUsersState(getState() as RootState);
    try {
      if (loading) {
        return;
      }

      dispatch(usersSlice.actions.setLoading(true));
      const response = await getUsers().then(({ data }) => data);
      dispatch(usersSlice.actions.setUsers(response));

    } catch (e) {
      const message =
        e instanceof Error ? e.message : `Unknown error in ${PREFFIX}/fetchAll`;
      dispatch(usersSlice.actions.setError(message));
    } finally {
      dispatch(usersSlice.actions.setLoading(false));
    }
  },
);
