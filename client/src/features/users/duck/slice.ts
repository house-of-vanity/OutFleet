import { createSlice } from '@reduxjs/toolkit';
import type { PayloadAction } from '@reduxjs/toolkit';
import type { UserDTO, User } from './dto';

export interface UsersState {
  loading: boolean;
  users: User[]
  error: null | string;
}

const initialState: UsersState = {
  loading: false,
  users: [],
  error: null,
};

export const usersSlice = createSlice({
  name: 'certificate',
  initialState,
  reducers: {
    setLoading: (state, action: PayloadAction<boolean>) => {
        state.loading = action.payload
    },
    setUsers: (state, action: PayloadAction<UserDTO[]>) => {
        state.users = action.payload.users
    },
    setError: (state, action: PayloadAction<string>) => {
        state.error = action.payload
    }
  },
});

