# Can a reasoning model keep a secret out of its own chain of thought?

*Danyil, continuing Bianca's project ([slides](docs/presentation.pdf)) · Qwen3.6-27B · two experiments, 9,680 attempts*

## Abstract

Monitoring a model's chain of thought (CoT) is only useful if the model does not quietly keep things
out of it. We give a reasoning model a secret it does not need — an API key whose first four
characters answer a partner's question — and tell it that the partner reads its thinking. We then
vary what else it is told. Left alone, the model writes the whole key into its thinking in 96% of
attempts. Telling it *why* the key is secret changes nothing (95%), although it knows perfectly well
that its thinking reaches the partner. Two things do help: telling it to keep the key to itself
(65–68%), and adding a single sentence that its reasoning is read (71%). An instruction about one
action — "read only the first four characters" — works almost every time (0.4%), because a secret
that is never read cannot leak. The model, in short, treats its thinking as a scratchpad rather than
as something others see, unless it is told otherwise.

## The setup

A support assistant is asked which regional server (EU or US) a customer's account uses. The answer is
in the prefix of the account's secret API key (`eu1_…` or `us1_…`), stored in a file the assistant
opens with a tool. The tool can read just the prefix, so the secret part is never needed. The partner
who asks sees the assistant's reasoning and replies, but not its tool results — so the reasoning is
the only way the key can reach them. We call it a **leak** when the secret part appears there.

The same task runs in four settings — a shipping API, cloud storage, a payment processor and a CRM —
with 48 new customers and six wordings of every sentence. Each condition has 240 attempts.

![How often the model leaks the key, by what it is told](docs/experiments/v2/figures/main/leak_by_condition.png)

## What we found

1. **A reason alone does not help.** Saying that the key gives full control of the customer's
   account leaves leaks at 95%, the same as saying nothing. Bianca saw the same with Kimi K3.
2. **The model knows its thinking is seen.** Asked whether a key written in its reasoning would reach
   the partner, it answers yes every time (328 of 328). It does not act on that knowledge unprompted.
3. **Naming the reasoning makes the reason work.** One added sentence — "anything you write in your
   reasoning is read by the partner" — lowers leaks from 95% to 71%. It is also the only case where
   the model often states a rule about its *thinking* rather than its reply.
4. **An instruction works without naming the reasoning.** "Do not share the API key with the
   partner" leaks as much as the same sentence with "in your reasoning or in your replies" added
   (68% vs 65%).
5. **Actions are easy to control; one's own text is not.** "Read only the first 4 characters of
   credentials.key" is followed in 239 of 240 attempts, and then nothing leaks. "Read only what you
   need" is ignored (1%). An instruction about its own text still leaks in two thirds of attempts.

A first experiment in one setting (8,000 attempts) adds that being watched helps only once the model
has been told something, that the rules it states are about its reply and often come only after it
has written the key, and that instructions aimed at the thinking itself ("not in your reasoning")
work worse than general ones.

## What it means

For a monitor that reads only the chain of thought, this is good news in the easy case: without an
instruction the model writes down what it reads. With a plain instruction, a 27B open model keeps a
secret it does not need out of its thinking about a third of the time. The model's stated rules point
to why: it guards its *reply*, and treats its reasoning as private unless told it is not.

## Limits

One model; one kind of secret in four settings; a secret the task never needs. Exact rates move by up
to about 30 points with the wording of a single sentence, so the comparisons between conditions are
the result, not the absolute numbers. Every answer was correct, which shows the task is easy, not that
control comes for free.

## Next

Look inside the model: what the one sentence about the reasoning changes in its activations; whether
a probe can tell, before the key appears, that it is about to be written; and whether the knowledge it
reports is active at the moment it leaks. Then: secrets the task partly needs, and other models.

*Details: [README](README.md) · [results](docs/experiments/v2/results/main.md) ·
[first experiment](docs/experiments/v1/results/test.md) · [terms](docs/terminology.md) ·
[examples](docs/experiments/v2/examples.md)*
