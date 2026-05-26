import { deleteThread, fetchThreads, type Thread } from "@/lib/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const THREADS_STALE_TIME_MS = 60_000;

export const threadsQueryKey = (userId: string | undefined) => ["threads", userId] as const;

export function useThreadsQuery(userId: string | undefined) {
	return useQuery({
		queryKey: threadsQueryKey(userId),
		queryFn: () => fetchThreads(undefined, userId),
		staleTime: THREADS_STALE_TIME_MS,
		enabled: Boolean(userId),
	});
}

export function useDeleteThreadMutation(userId: string | undefined) {
	const queryClient = useQueryClient();
	const key = threadsQueryKey(userId);

	return useMutation({
		mutationFn: (threadId: string) => deleteThread(threadId, userId),
		onMutate: async (threadId) => {
			await queryClient.cancelQueries({ queryKey: key });
			const previous = queryClient.getQueryData<Thread[]>(key);
			queryClient.setQueryData<Thread[]>(key, (old) =>
				(old ?? []).filter((t) => t.thread_id !== threadId)
			);
			return { previous };
		},
		onError: (_err, _threadId, context) => {
			if (context?.previous) {
				queryClient.setQueryData(key, context.previous);
			}
		},
		onSettled: () => {
			void queryClient.invalidateQueries({ queryKey: key });
		},
	});
}
