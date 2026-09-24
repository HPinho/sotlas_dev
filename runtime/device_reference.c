/* device_reference.c — deterministic conformance runtime for DEVICE ABI v1. */
#include "device_reference.h"

#define SOTLAS_DEVICE_REFERENCE_MAX_SUBMISSIONS 64u
#define SOTLAS_DEVICE_REFERENCE_MAX_FENCES 32u

typedef enum reference_submission_state {
    REFERENCE_SUBMISSION_UNUSED = 0,
    REFERENCE_SUBMISSION_SUBMITTED = 1,
    REFERENCE_SUBMISSION_COMPLETED = 2,
    REFERENCE_SUBMISSION_SYNCHRONIZED = 3,
    REFERENCE_SUBMISSION_REACQUIRED = 4
} reference_submission_state_t;

typedef struct reference_submission {
    sotlas_device_queue_t queue;
    uintptr_t host_address;
    size_t host_extent;
    uintptr_t device_address;
    size_t device_extent;
    reference_submission_state_t state;
} reference_submission_t;

typedef struct reference_fence {
    sotlas_device_queue_t queue;
    size_t count;
    sotlas_device_submission_t submissions[SOTLAS_DEVICE_REFERENCE_MAX_SUBMISSIONS];
    int active;
    int consumed;
} reference_fence_t;

static reference_submission_t s_submissions[SOTLAS_DEVICE_REFERENCE_MAX_SUBMISSIONS];
static reference_fence_t s_fences[SOTLAS_DEVICE_REFERENCE_MAX_FENCES];
static size_t s_submission_count = 0;
static size_t s_fence_count = 0;
static sotlas_device_reference_status_t s_last_status = SOTLAS_DEVICE_REFERENCE_OK;

static void reference_set_status(sotlas_device_reference_status_t status) {
    s_last_status = status;
}

static reference_submission_t *reference_submission_from_token(
    sotlas_device_submission_t token
) {
    size_t index;
    if (token == 0) return NULL;
    index = (size_t)(token - 1u);
    if (index >= s_submission_count) return NULL;
    if (s_submissions[index].state == REFERENCE_SUBMISSION_UNUSED) return NULL;
    return &s_submissions[index];
}

static reference_fence_t *reference_fence_from_token(sotlas_device_fence_t token) {
    size_t index;
    if (token == 0) return NULL;
    index = (size_t)(token - 1u);
    if (index >= s_fence_count) return NULL;
    if (!s_fences[index].active) return NULL;
    return &s_fences[index];
}

void sotlas_device_reference_reset(void) {
    size_t i;
    size_t j;
    for (i = 0; i < SOTLAS_DEVICE_REFERENCE_MAX_SUBMISSIONS; ++i) {
        s_submissions[i].queue = 0;
        s_submissions[i].host_address = 0;
        s_submissions[i].host_extent = 0;
        s_submissions[i].device_address = 0;
        s_submissions[i].device_extent = 0;
        s_submissions[i].state = REFERENCE_SUBMISSION_UNUSED;
    }
    for (i = 0; i < SOTLAS_DEVICE_REFERENCE_MAX_FENCES; ++i) {
        s_fences[i].queue = 0;
        s_fences[i].count = 0;
        s_fences[i].active = 0;
        s_fences[i].consumed = 0;
        for (j = 0; j < SOTLAS_DEVICE_REFERENCE_MAX_SUBMISSIONS; ++j) {
            s_fences[i].submissions[j] = 0;
        }
    }
    s_submission_count = 0;
    s_fence_count = 0;
    reference_set_status(SOTLAS_DEVICE_REFERENCE_OK);
}

sotlas_device_reference_status_t sotlas_device_reference_last_status(void) {
    return s_last_status;
}

int sotlas_device_reference_fence_consumed(sotlas_device_fence_t fence) {
    reference_fence_t *entry = reference_fence_from_token(fence);
    if (!entry) {
        reference_set_status(SOTLAS_DEVICE_REFERENCE_UNKNOWN_FENCE);
        return 0;
    }
    reference_set_status(SOTLAS_DEVICE_REFERENCE_OK);
    return entry->consumed ? 1 : 0;
}

sotlas_device_submission_t sotlas_device_submit(
    sotlas_device_queue_t queue,
    uintptr_t host_address,
    size_t host_extent,
    uintptr_t *out_device_address,
    size_t *out_device_extent
) {
    reference_submission_t *entry;
    sotlas_device_submission_t token;

    if (queue == 0 || out_device_address == NULL || out_device_extent == NULL) {
        reference_set_status(SOTLAS_DEVICE_REFERENCE_INVALID_ARGUMENT);
        return 0;
    }
    if (s_submission_count >= SOTLAS_DEVICE_REFERENCE_MAX_SUBMISSIONS) {
        reference_set_status(SOTLAS_DEVICE_REFERENCE_CAPACITY_EXHAUSTED);
        return 0;
    }

    entry = &s_submissions[s_submission_count];
    entry->queue = queue;
    entry->host_address = host_address;
    entry->host_extent = host_extent;
    /* Conformance provider preserves identity; it does not move/copy bytes. */
    entry->device_address = host_address;
    entry->device_extent = host_extent;
    entry->state = REFERENCE_SUBMISSION_SUBMITTED;

    *out_device_address = entry->device_address;
    *out_device_extent = entry->device_extent;
    token = (sotlas_device_submission_t)(s_submission_count + 1u);
    ++s_submission_count;
    reference_set_status(SOTLAS_DEVICE_REFERENCE_OK);
    return token;
}

sotlas_device_completion_t sotlas_device_complete(
    sotlas_device_queue_t queue,
    sotlas_device_submission_t submission
) {
    reference_submission_t *entry = reference_submission_from_token(submission);
    if (!entry) {
        reference_set_status(SOTLAS_DEVICE_REFERENCE_UNKNOWN_SUBMISSION);
        return 0;
    }
    if (entry->queue != queue) {
        reference_set_status(SOTLAS_DEVICE_REFERENCE_QUEUE_MISMATCH);
        return 0;
    }
    if (entry->state != REFERENCE_SUBMISSION_SUBMITTED) {
        reference_set_status(SOTLAS_DEVICE_REFERENCE_INVALID_STATE);
        return 0;
    }
    entry->state = REFERENCE_SUBMISSION_COMPLETED;
    reference_set_status(SOTLAS_DEVICE_REFERENCE_OK);
    /* Completion and submission are distinct semantic types but share v1 bits. */
    return (sotlas_device_completion_t)submission;
}

sotlas_device_fence_t sotlas_device_sync(
    sotlas_device_queue_t queue,
    const sotlas_device_completion_t *completions,
    size_t completion_count
) {
    reference_fence_t *fence;
    size_t i;
    size_t j;

    if (queue == 0 || completions == NULL || completion_count == 0
        || completion_count > SOTLAS_DEVICE_REFERENCE_MAX_SUBMISSIONS) {
        reference_set_status(SOTLAS_DEVICE_REFERENCE_INVALID_ARGUMENT);
        return 0;
    }
    if (s_fence_count >= SOTLAS_DEVICE_REFERENCE_MAX_FENCES) {
        reference_set_status(SOTLAS_DEVICE_REFERENCE_CAPACITY_EXHAUSTED);
        return 0;
    }

    /* Validate the entire set before mutating any submission state. */
    for (i = 0; i < completion_count; ++i) {
        reference_submission_t *entry = reference_submission_from_token(
            (sotlas_device_submission_t)completions[i]
        );
        if (!entry) {
            reference_set_status(SOTLAS_DEVICE_REFERENCE_UNKNOWN_SUBMISSION);
            return 0;
        }
        if (entry->queue != queue) {
            reference_set_status(SOTLAS_DEVICE_REFERENCE_QUEUE_MISMATCH);
            return 0;
        }
        if (entry->state != REFERENCE_SUBMISSION_COMPLETED) {
            reference_set_status(SOTLAS_DEVICE_REFERENCE_INVALID_STATE);
            return 0;
        }
        for (j = 0; j < i; ++j) {
            if (completions[j] == completions[i]) {
                reference_set_status(SOTLAS_DEVICE_REFERENCE_DUPLICATE_COMPLETION);
                return 0;
            }
        }
    }

    fence = &s_fences[s_fence_count];
    fence->queue = queue;
    fence->count = completion_count;
    fence->active = 1;
    fence->consumed = 0;
    for (i = 0; i < completion_count; ++i) {
        reference_submission_t *entry = reference_submission_from_token(
            (sotlas_device_submission_t)completions[i]
        );
        fence->submissions[i] = (sotlas_device_submission_t)completions[i];
        entry->state = REFERENCE_SUBMISSION_SYNCHRONIZED;
    }

    ++s_fence_count;
    reference_set_status(SOTLAS_DEVICE_REFERENCE_OK);
    return (sotlas_device_fence_t)s_fence_count;
}

void sotlas_device_reacquire(
    sotlas_device_queue_t queue,
    uintptr_t device_address,
    size_t device_extent,
    sotlas_device_fence_t fence_token,
    uintptr_t *out_host_address,
    size_t *out_host_extent
) {
    reference_fence_t *fence;
    reference_submission_t *matched = NULL;
    size_t i;
    size_t remaining = 0;

    if (queue == 0 || out_host_address == NULL || out_host_extent == NULL) {
        reference_set_status(SOTLAS_DEVICE_REFERENCE_INVALID_ARGUMENT);
        return;
    }
    fence = reference_fence_from_token(fence_token);
    if (!fence) {
        reference_set_status(SOTLAS_DEVICE_REFERENCE_UNKNOWN_FENCE);
        return;
    }
    if (fence->queue != queue) {
        reference_set_status(SOTLAS_DEVICE_REFERENCE_QUEUE_MISMATCH);
        return;
    }
    if (fence->consumed) {
        reference_set_status(SOTLAS_DEVICE_REFERENCE_INVALID_STATE);
        return;
    }

    for (i = 0; i < fence->count; ++i) {
        reference_submission_t *entry = reference_submission_from_token(
            fence->submissions[i]
        );
        if (!entry) continue;
        if (entry->state == REFERENCE_SUBMISSION_SYNCHRONIZED
            && entry->device_address == device_address
            && entry->device_extent == device_extent) {
            matched = entry;
            break;
        }
    }
    if (!matched) {
        reference_set_status(SOTLAS_DEVICE_REFERENCE_OWNER_NOT_IN_FENCE);
        return;
    }

    *out_host_address = matched->host_address;
    *out_host_extent = matched->host_extent;
    matched->state = REFERENCE_SUBMISSION_REACQUIRED;

    for (i = 0; i < fence->count; ++i) {
        reference_submission_t *entry = reference_submission_from_token(
            fence->submissions[i]
        );
        if (entry && entry->state != REFERENCE_SUBMISSION_REACQUIRED) {
            ++remaining;
        }
    }
    if (remaining == 0) {
        fence->consumed = 1;
    }
    reference_set_status(SOTLAS_DEVICE_REFERENCE_OK);
}
