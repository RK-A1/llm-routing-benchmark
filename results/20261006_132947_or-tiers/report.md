# Results

Runs: 20261006_132947_or-tiers, 20261006_133245_or-max-c2

## Accuracy %

| config         |   easy |   medium |   hard |   expert |   all |
|:---------------|-------:|---------:|-------:|---------:|------:|
| or-auto-high   |    100 |      100 |    100 |      100 |   100 |
| or-auto-max    |    100 |      100 |    100 |      100 |   100 |
| or-auto-medium |    100 |      100 |     75 |      100 |    96 |
| or-auto-xhigh  |    100 |      100 |     75 |      100 |    96 |

## Cost

| config         |   answers |   correct |   total $ |   LiteLLM-reported $ |   $ / correct answer |   $ / answer |   LLM calls / answer |   LLM seconds / answer |
|:---------------|----------:|----------:|----------:|---------------------:|---------------------:|-------------:|---------------------:|-----------------------:|
| or-auto-high   |        24 |        24 |     0.541 |                0.541 |               0.0225 |       0.0225 |                  2.8 |                    7.2 |
| or-auto-max    |         6 |         6 |     0.806 |                0.806 |               0.1343 |       0.1343 |                  2.7 |                   17   |
| or-auto-medium |        24 |        23 |     0.134 |                0.134 |               0.0058 |       0.0056 |                  3.1 |                    6.8 |
| or-auto-xhigh  |        24 |        23 |     1.069 |                1.069 |               0.0465 |       0.0445 |                  2.9 |                    7.3 |

## Routing threshold: model on each turn's first call, by tier

| config         | easy                         | medium                 | hard                                   | expert                       |
|:---------------|:-----------------------------|:-----------------------|:---------------------------------------|:-----------------------------|
| or-auto-high   | claude-sonnet-5.5 100%       | claude-sonnet-5.5 100% | claude-sonnet-5.5 50%, gpt-6.1-sol 50% | claude-sonnet-5.5 100%       |
| or-auto-max    | gpt-6-astra-pro 100%         | gpt-6-astra-pro 100%   | gpt-6-astra-pro 100%                   | gpt-6-astra-pro 100%         |
| or-auto-medium | glm-5.2 75%, gpt-6.1-sol 25% | glm-5.2 100%           | glm-5.2 50%, gpt-6.1-sol 50%           | glm-5.2 50%, gpt-6.1-sol 50% |
| or-auto-xhigh  | claude-opus-5.5 100%         | claude-opus-5.5 100%   | claude-opus-5.5 100%                   | claude-opus-5.5 100%         |

## Routing behaviour

| config         |   answers with a switch inside the tool loop % |   conversations whose turns start on different models % | turns that start on the same model in every repeat %   |
|:---------------|-----------------------------------------------:|--------------------------------------------------------:|:-------------------------------------------------------|
| or-auto-high   |                                              0 |                                                      50 |                                                        |
| or-auto-max    |                                              0 |                                                       0 |                                                        |
| or-auto-medium |                                              4 |                                                      50 |                                                        |
| or-auto-xhigh  |                                              0 |                                                       0 |                                                        |

## Failure modes (wrong answers by cause, plus counters)

| config         |   final SQL error |   wrong result |   nudged |   SQL errors |   repeated SQL |
|:---------------|------------------:|---------------:|---------:|-------------:|---------------:|
| or-auto-medium |                 0 |              1 |        0 |            1 |              1 |
| or-auto-xhigh  |                 1 |              0 |        0 |            2 |              0 |

## Accuracy % per question

|                    |   or-auto-high |   or-auto-max |   or-auto-medium |   or-auto-xhigh |
|:-------------------|---------------:|--------------:|-----------------:|----------------:|
| ('easy', 'c1.1')   |            100 |           nan |              100 |             100 |
| ('easy', 'c1.4')   |            100 |           nan |              100 |             100 |
| ('easy', 'c1.6')   |            100 |           nan |              100 |             100 |
| ('easy', 'c2.1')   |            100 |           100 |              100 |             100 |
| ('easy', 'c2.4')   |            100 |           100 |              100 |             100 |
| ('easy', 'c2.6')   |            100 |           100 |              100 |             100 |
| ('easy', 'c3.1')   |            100 |           nan |              100 |             100 |
| ('easy', 'c3.4')   |            100 |           nan |              100 |             100 |
| ('easy', 'c3.6')   |            100 |           nan |              100 |             100 |
| ('easy', 'c4.1')   |            100 |           nan |              100 |             100 |
| ('easy', 'c4.4')   |            100 |           nan |              100 |             100 |
| ('easy', 'c4.6')   |            100 |           nan |              100 |             100 |
| ('medium', 'c1.2') |            100 |           nan |              100 |             100 |
| ('medium', 'c2.2') |            100 |           100 |              100 |             100 |
| ('medium', 'c3.2') |            100 |           nan |              100 |             100 |
| ('medium', 'c4.2') |            100 |           nan |              100 |             100 |
| ('hard', 'c1.3')   |            100 |           nan |                0 |             100 |
| ('hard', 'c2.3')   |            100 |           100 |              100 |               0 |
| ('hard', 'c3.3')   |            100 |           nan |              100 |             100 |
| ('hard', 'c4.3')   |            100 |           nan |              100 |             100 |
| ('expert', 'c1.5') |            100 |           nan |              100 |             100 |
| ('expert', 'c2.5') |            100 |           100 |              100 |             100 |
| ('expert', 'c3.5') |            100 |           nan |              100 |             100 |
| ('expert', 'c4.5') |            100 |           nan |              100 |             100 |
