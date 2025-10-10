import { templatesSlice } from './slice';
import { getTemplates } from './api';
import { createAsyncThunk } from '@reduxjs/toolkit';
import { getTemplatesState } from './selectors';
import type { RootState } from '../../../store';

const PREFFIX = 'templates';

export const fetchTemplates = createAsyncThunk(
  `${PREFFIX}/fetchAll`,
  async (_, { dispatch, getState }) => {
    const { loading } = getTemplatesState(getState() as RootState);
    try {
      if (loading) {
        return;
      }

      dispatch(templatesSlice.actions.setLoading(true));
      const response = await getTemplates().then(({ data }) => data);
      dispatch(templatesSlice.actions.setTemplates(response));
    } catch (e) {
      const message =
        e instanceof Error ? e.message : `Unknown error in ${PREFFIX}/fetchAll`;
      dispatch(templatesSlice.actions.setError(message));
    } finally {
      dispatch(templatesSlice.actions.setLoading(false));
    }
  },
);
