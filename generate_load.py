import argparse
import math
import multiprocessing
import random
import threading
import time
from datetime import datetime

import braintrust
import tiktoken
from faker import Faker

import monkey_patch  # noqa: F401

APPS = ["mobile", "web", "backend", "frontend", "api", "cli", "other"]
REGIONS = ["us-west", "us-east", "eu-west", "eu-east", "ap-southeast", "ap-northeast"]
USER_TENURE = ["new", "returning", "loyal"]


def generate_n_tokens(tokenizer, fake, tokens):
    words = fake.sentence(tokens * 2)
    tokens = tokenizer.encode(words)[:tokens]
    return tokenizer.decode(tokens), len(tokens)


def run_request():
    input_text, input_text_tokens = generate_n_tokens(
        tokenizer,
        fake,
        math.ceil(user_tokens_target * (1 + args.jitter * (random.random() - 0.5))),
    )
    output_text, output_text_tokens = generate_n_tokens(
        tokenizer,
        fake,
        math.ceil(
            completion_tokens_target * (1 + args.jitter * (random.random() - 0.5))
        ),
    )

    pretend_duration = random.random() * 120
    pretend_offset = random.random() * 3600 * 24 * 30
    pretend_start = time.time() - pretend_offset - pretend_duration

    start_ts = datetime.fromtimestamp(pretend_start).isoformat()

    current_span = logger
    spans = []
    for i in range(args.spans_per_request - 1):
        scores = {}
        tags = []
        metadata = {}
        if i == 0:
            if random.random() < args.sampling_rate:
                scores["Factuality"] = random.random()
                tags.append("Sampled")
            if random.random() < args.sampling_rate:
                tags.append("Toxic")
                scores["Toxicity"] = random.random() / 5
            if random.random() < args.sampling_rate:
                tags.append("Triage")
                scores["Preference"] = random.random()

            scores["Quality"] = random.random()

        metadata["app"] = random.choice(APPS)
        metadata["region"] = random.choice(REGIONS)
        metadata["user_tenure"] = random.choice(USER_TENURE)

        span = current_span.start_span(
            name=f"span-{i}",
            span_attributes={"type": "function"},
            start_time=pretend_start,
            scores=scores,
            tags=tags or None,
            metadata=metadata,
            created=start_ts,
        )
        span.log(input=input_text)
        spans.append(span)
        current_span = span

    oai_span = current_span.start_span(
        name="openai",
        span_attributes={"type": "llm"},
        start_time=pretend_start,
        created=start_ts,
    )
    oai_span.log(
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_text},
        ],
        output=output_text,
        metadata={
            "model": args.encoding_model,
            "temperature": 0.7,
        },
        metrics={
            "prompt_tokens": system_prompt_tokens + input_text_tokens,
            "completion_tokens": output_text_tokens,
            "total_tokens": system_prompt_tokens
            + input_text_tokens
            + output_text_tokens,
            "tokens": system_prompt_tokens
            + input_text_tokens
            + output_text_tokens,
            "time_to_first_token": pretend_duration / random.randint(2, 10),
        },
    )
    oai_span.end(end_time=pretend_start + pretend_duration)

    for span in reversed(spans):
        span.log(output=output_text)
        span.end(end_time=pretend_start + pretend_duration)


global_total = 0
global_total_lock = threading.Lock()


def runner_thread(idx, total_requests):
    global global_total

    total_flushed = 0
    start = time.time()
    for i in range(total_requests):
        run_request()

        with global_total_lock:
            global_total += 1

        if (i + 1) % args.flush_interval == 0 or i == total_requests - 1:
            pre_flush = time.time()
            logger.flush()
            post_flush = time.time()
            new_total = i + 1

            process_time = pre_flush - start
            flush_time = post_flush - pre_flush
            print(
                f"Thread {idx:<3} processed {new_total - total_flushed:<3} requests ({new_total} / {total_requests}).    "
                f"Processing time: {process_time:>6.2f}s.    "
                f"Flush time: {flush_time:>6.2f}s.    "
                f"Batch req/s: {(new_total - total_flushed) / flush_time:>8.2f}.    "
                f"Total req/s: {new_total / (post_flush - start):>8.2f}    "
                f"Target req/s: {args.requests_per_day / 86400:>8.2f}    "
            )

            total_flushed = new_total

    logger.flush()


def reporter_thread(done):
    start = time.time()
    last_measure = start
    last_total = 0
    while not done["done"]:
        time.sleep(2)
        diff = global_total - last_total
        current_time = time.time()
        diff_time = current_time - last_measure
        total_time = current_time - start

        rate = diff / diff_time
        total_rate = global_total / total_time

        last_measure = current_time
        last_total = global_total

        print(
            f"-- Processed {diff:<3} requests in {diff_time:>6.2f}s.    "
            f"Rate: {rate:>8.2f} requests/s.    "
            f"Total rate: {total_rate:>8.2f} requests/s."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate load")
    parser.add_argument(
        "--total-requests",
        type=int,
        default=100,
        help="Total number of requests before quitting",
    )
    parser.add_argument(
        "--requests-per-day",
        type=int,
        default=100000,
        help="Number of requests per day",
    )
    parser.add_argument(
        "--tokens-per-request",
        type=int,
        default=1000,
        help="Target number of tokens per request",
    )
    parser.add_argument(
        "--jitter",
        type=float,
        default=0.1,
        help="Jitter in the number of tokens per request",
    )
    parser.add_argument(
        "--spans-per-request",
        type=int,
        default=3,
        help="Number of spans per request",
    )
    parser.add_argument(
        "--sampling-rate",
        type=float,
        default=0.1,
        help="Sampling rate for tags",
    )
    parser.add_argument(
        "--flush-interval",
        type=int,
        default=100,
        help="Flush every N requests",
    )
    parser.add_argument(
        "--project-name",
        type=str,
        default="load-test",
        help="Project name",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed",
    )
    parser.add_argument(
        "--encoding-model",
        type=str,
        default="gpt-3.5-turbo",
        help="Encoding model",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=multiprocessing.cpu_count(),
        help="Number of threads",
    )

    args = parser.parse_args()

    fake = Faker()
    Faker.seed(args.seed)
    random.seed(args.seed)

    # Split it up so that 50% of the tokens go to a system prompt,
    # 20% to a user prompt, and 30% to the assistant response.
    tokenizer = tiktoken.encoding_for_model(args.encoding_model)

    system_prompt, system_prompt_tokens = generate_n_tokens(
        tokenizer, fake, math.ceil(0.5 * args.tokens_per_request)
    )
    user_tokens_target = math.ceil(0.2 * args.tokens_per_request)
    completion_tokens_target = math.ceil(0.3 * args.tokens_per_request)

    braintrust.login()
    logger = braintrust.init_logger(project=args.project_name)

    start = time.time()
    done = {"done": False}
    reporter = threading.Thread(target=reporter_thread, args=(done,))
    reporter.start()
    if args.threads == 1:
        runner_thread(0, args.total_requests)
    else:
        threads = []
        for i in range(args.threads):
            thread = threading.Thread(
                target=runner_thread,
                args=(i, math.ceil(args.total_requests / args.threads)),
            )
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

    print(f"Total time: {time.time() - start}")

    done["done"] = True
    reporter.join()
