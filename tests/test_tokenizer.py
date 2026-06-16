from nbrag.tokenizer import tokenize_all, tokenize_cjk_ngram, tokenize_code, tokenize_word


def test_tokenize_code_identifier_variants_without_cjk():
    tokens = tokenize_code("class RedisQueuePublisher: REDIS_BULK_PUSH = 'redis'")

    assert "redisqueuepublisher" in tokens
    assert "redis" in tokens
    assert "queue" in tokens
    assert "publisher" in tokens
    assert "redis_bulk_push" in tokens
    assert "bulk" in tokens
    assert "push" in tokens


def test_tokenize_chinese_word_and_ngram_for_mixed_code_docs():
    text = "funboost 发布任务到 redis 队列，支持分布式消费和失败重试"

    word_tokens = tokenize_word(text)
    ngram_tokens = tokenize_cjk_ngram(text)
    all_tokens = tokenize_all(text)

    assert "funboost" in word_tokens
    assert "redis" in word_tokens
    assert any(token in word_tokens for token in ("队列", "分布式", "失败", "重试"))
    assert "队列" in ngram_tokens
    assert "失败" in ngram_tokens
    assert "word" in all_tokens and "ngram" in all_tokens and "code" in all_tokens


def test_tokenize_chinese_ngram_keeps_short_phrase_overlap():
    tokens = tokenize_cjk_ngram("试用期不得超过二个月")

    assert "试用" in tokens
    assert "不得" in tokens
    assert "超过" in tokens
    assert "试用期" in tokens
    assert "不得超" in tokens
