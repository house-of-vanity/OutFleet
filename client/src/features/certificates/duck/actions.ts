import { certificateSlice } from './slice';
import { createCertificate, deleteCertificate, getCertificates, patchCertificate } from './api';
import { createAsyncThunk } from '@reduxjs/toolkit';
import { getCertificatesState } from './selectors';
import type { RootState } from '../../../store';
import { appNotificator } from '../../../utils/notification/app-notificator';
import type { CreateCertificateDTO, EditCertificateDTO } from './dto';

const PREFFIX = 'certificates';

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

export const createCertificateAction = createAsyncThunk(
  `${PREFFIX}/createCertificates`,
  async (params: CreateCertificateDTO, { dispatch }) => {
    try {
      await createCertificate(params);
      dispatch(fetchCertificates());
    } catch (e) {
      appNotificator.add({
        message:
          e instanceof Error
            ? e.message
            : `Unknown error in ${PREFFIX}/createCertificates`,
        type: 'error',
      });
    }
  },
);

export const updateCertificate = createAsyncThunk(
  `${PREFFIX}/updateCertificate`,
  async (
    params: {
      id: string;
      certificate: EditCertificateDTO;
    },
    { dispatch },
  ) => {
    try {
      await patchCertificate(params.id, params.certificate);
      dispatch(fetchCertificates());
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

export const deleteCertificateAction = createAsyncThunk(
  `${PREFFIX}/deleteCertificate`,
  async (id: string, { dispatch }) => {
    try {
      await deleteCertificate(id);
      appNotificator.add({
        message: 'Certificate deleted',
        type: 'success',
      });
      dispatch(fetchCertificates());
    } catch (e) {
      appNotificator.add({
        type: 'error',
        message:
          e instanceof Error
            ? `Delete error: ${e.message}`
            : `Unknown error in ${PREFFIX}/deleteCertificate`,
      });
    }
  },
);