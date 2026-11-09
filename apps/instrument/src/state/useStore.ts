import { createContext, useContext, useSyncExternalStore } from "react";
import type { InstrumentStore, State } from "./store";

export const StoreContext = createContext<InstrumentStore | null>(null);

export function useStore(): InstrumentStore {
  const store = useContext(StoreContext);
  if (!store) throw new Error("StoreContext is missing");
  return store;
}

export function useInstrumentState(): State {
  const store = useStore();
  return useSyncExternalStore(store.subscribe, store.getState, store.getState);
}
