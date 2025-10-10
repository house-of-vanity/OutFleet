import { configureStore, combineReducers } from '@reduxjs/toolkit'
import {serversSlice, templatesSlice, certificateSlice, usersSlice} from '../features'

export const store = configureStore({
  reducer: combineReducers({
    servers: serversSlice.reducer,
    templates: templatesSlice.reducer,
    users: usersSlice.reducer,
    certificates: certificateSlice.reducer
  }),
})

// Infer the `RootState` and `AppDispatch` types from the store itself
export type RootState = ReturnType<typeof store.getState>
// Inferred type: {posts: PostsState, comments: CommentsState, users: UsersState}
export type AppDispatch = typeof store.dispatch