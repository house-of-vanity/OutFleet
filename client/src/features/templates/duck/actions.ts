import { templatesSlice } from './slice';
import { getTemplates, createTemplate, patchTemplate, deleteTemplate } from './api';
import { createAsyncThunk } from '@reduxjs/toolkit';
import { getTemplatesState } from './selectors';
import type { RootState } from '../../../store';
import type { CreateTemplateDTO, EditTemplateDTO } from './dto';
import { appNotificator } from '../../../utils/notification/app-notificator';

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


export const createTemplateAction = createAsyncThunk(
  `${PREFFIX}/createTemplate`,
  async (params: CreateTemplateDTO, { dispatch }) => {
    try {
      await createTemplate(params);
      dispatch(fetchTemplates());
    } catch (e) {
      appNotificator.add({
        message:
          e instanceof Error
            ? e.message
            : `Unknown error in ${PREFFIX}/createTemplate`,
        type: 'error',
      });
    }
  },
);



export const updateTemplate = createAsyncThunk(
  `${PREFFIX}/updateTemplate`,
  async (
    params: {
      id: string;
      template: EditTemplateDTO;
    },
    { dispatch },
  ) => {
    try {
      await patchTemplate(params.id, params.template);
      dispatch(fetchTemplates());
      appNotificator.add({
        message: 'Template updated',
        type: 'success',
      });
    } catch (e) {
      appNotificator.add({
        type: 'error',
        message:
          e instanceof Error
            ? `Error updating: ${e.message}`
            : `Unknown error in ${PREFFIX}/updateTemplate`,
      });
    }
  },
);

export const deleteTemplateAction = createAsyncThunk(
  `${PREFFIX}/deleteTemplate`,
  async (id: string, { dispatch }) => {
    try {
      await deleteTemplate(id);
      appNotificator.add({
        message: 'Template deleted',
        type: 'success',
      });
      dispatch(fetchTemplates());
    } catch (e) {
      appNotificator.add({
        type: 'error',
        message:
          e instanceof Error
            ? `Delete error: ${e.message}`
            : `Unknown error in ${PREFFIX}/deleteTemplate`,
      });
    }
  },
);