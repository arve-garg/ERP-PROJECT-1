import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error) => {
        if (error instanceof Error && error.message.includes("(401)"))
          return false;
        return failureCount < 2;
      },
      refetchOnWindowFocus: false,
    },
  },
});
