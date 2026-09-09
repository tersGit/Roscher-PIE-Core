# V4B SmolVLM inference audit

## Scope and frozen boundary

This is a neutral-control runtime diagnostic. The immutable v4 blind freeze is commit
`3a4c57aee086a4b5389e6a9fe08283c4ff39e7c4`; no v4 artifact was modified. No listing
media was opened or rerun. The only frozen data read was the two raw-output JSONL files
as text records, recorded with hashes in `frozen_raw_forensic_references.json`.

## Exact v4 path

`scripts/lvi_v4_execute_blind.py` loads
`Idefics3ForConditionalGeneration.from_pretrained("HuggingFaceTB/SmolVLM-256M-Instruct",
revision="7e3e67edbbed1bf9888184d9df282b700a323964", torch_dtype=torch.float32).eval()`
and `AutoProcessor` at that same revision. In this runtime these resolve to
`Idefics3ForConditionalGeneration`, `Idefics3Processor`, and
`Idefics3ImageProcessor`, on CPU FP32.

For each image, v4 builds exactly one user message: a `{"type": "image"}` content item
followed by `{"type": "text", "text": PROMPT}`. It calls
`processor.apply_chat_template(messages, add_generation_prompt=True)`, passes that text
and a matching one-element RGB PIL image list to `processor(..., return_tensors="pt")`,
and sends tensors to CPU. The matching multi-image form contains four image items followed
by the text prompt and passes four RGB images in the same order.

The checkpoint template used by V4B renders the single-image form as:

```text
<|im_start|>User:<image>{prompt}<end_of_utterance>
Assistant:
```

Thus image placeholders are in the chat text, `add_generation_prompt=True` supplies the
assistant turn, and image binding is positional and valid for this checkpoint interface.
There is no separate tokenizer call: processor tokenization is part of the processor call.
The processor RGB-converts, splits, resizes, normalizes, pads, and rescales images. Its
recorded settings include a longest edge of 512 for image splitting and mean/std of 0.5.

Generation is greedy (`do_sample=False`, `num_beams=1`, `max_new_tokens=500`). It does not
set temperature, repetition penalty, minimum tokens, custom stopping criteria, or EOS; the
checkpoint generation configuration supplies EOS ID 49279. v4 removes the input prefix with
`output[:, inputs["input_ids"].shape[1]:]` before
`processor.batch_decode(..., skip_special_tokens=True)`. It does not otherwise truncate
decoded output. JSON parsing first tries the whole response, then the first brace-delimited
substring. Only parseable dictionary-valued feature entries become normalized observations.

## Retained classification-oriented prompt defect

The v4 single-frame prompt demands a large JSON object with 13 named property fields, each
requiring four subfields and two prescribed status labels. The multi-frame prompt likewise
demands a relationship JSON object and repeatedly foregrounds
`UNKNOWN_NOT_VISIBLE`. That high-constraint classification/schema prompt was retained rather
than first establishing the model's free visual-description competence. It is unsuitable for
this 256M checkpoint, but it is not a chat-template, image-binding, token-removal, or JSON
post-processing defect.

## Runtime warning

Transformers 5.14.1 emitted a model-config warning that a `pad_token_id` of 128002 is outside
the vocabulary, while the loaded generation configuration exposes pad ID 2 and EOS ID 49279.
This is recorded as a compatibility risk. It does not explain the short v4 outputs: V4B got
both natural-EOS short answers and max-token long answers from the same path.
