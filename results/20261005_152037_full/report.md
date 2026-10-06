# Results

Runs: 20261005_152037_full, 20261005_143531_calib-v3

## Accuracy %

| config             |   easy |   medium |   hard |   expert |   all |
|:-------------------|-------:|---------:|-------:|---------:|------:|
| claude-opus        |    100 |      100 |    100 |       75 |    96 |
| fw-auto            |    100 |      100 |    100 |      100 |   100 |
| fw-firerouter-opus |    100 |      100 |    100 |       83 |    97 |
| glm-flash          |    100 |      100 |     88 |      100 |    98 |
| or-auto            |    100 |      100 |    100 |      100 |   100 |

## Cost

| config             |   answers |   correct |   total $ |   LiteLLM-reported $ |   $ / correct answer |   $ / answer |   LLM calls / answer |   LLM seconds / answer |
|:-------------------|----------:|----------:|----------:|---------------------:|---------------------:|-------------:|---------------------:|-----------------------:|
| claude-opus        |        24 |        23 |     1.103 |                1.103 |               0.048  |       0.046  |                  2.8 |                    7.5 |
| fw-auto            |        72 |        72 |     0.304 |                0.304 |               0.0042 |       0.0042 |                  3.1 |                    9.9 |
| fw-firerouter-opus |        72 |        70 |     0.302 |                0.302 |               0.0043 |       0.0042 |                  3.2 |                   11.2 |
| glm-flash          |        48 |        47 |     0.052 |                0.052 |               0.0011 |       0.0011 |                  3.5 |                    9.6 |
| or-auto            |        72 |        72 |     0.09  |                0.09  |               0.0012 |       0.0013 |                  3.5 |                    3.8 |

## Routing threshold: model on each turn's first call, by tier

| config             | easy                          | medium                   | hard                     | expert                   |
|:-------------------|:------------------------------|:-------------------------|:-------------------------|:-------------------------|
| claude-opus        | claude-opus-5-5 100%          | claude-opus-5-5 100%     | claude-opus-5-5 100%     | claude-opus-5-5 100%     |
| fw-auto            | glm-5p3 97%, glm-5p3-flash 3% | glm-5p3 100%             | glm-5p3 100%             | glm-5p3 100%             |
| fw-firerouter-opus | glm-5p3 94%, glm-5p3-flash 6% | glm-5p3 100%             | glm-5p3 100%             | glm-5p3 100%             |
| glm-flash          | glm-5p3-flash 100%            | glm-5p3-flash 100%       | glm-5p3-flash 100%       | glm-5p3-flash 100%       |
| or-auto            | deepseek-v4.1-flash 100%      | deepseek-v4.1-flash 100% | deepseek-v4.1-flash 100% | deepseek-v4.1-flash 100% |

## Routing behaviour

| config             |   answers with a switch inside the tool loop % |   conversations whose turns start on different models % |   turns that start on the same model in every repeat % |
|:-------------------|-----------------------------------------------:|--------------------------------------------------------:|-------------------------------------------------------:|
| claude-opus        |                                              0 |                                                       0 |                                                    100 |
| fw-auto            |                                              3 |                                                       8 |                                                     96 |
| fw-firerouter-opus |                                              3 |                                                       8 |                                                     92 |
| glm-flash          |                                              0 |                                                       0 |                                                    100 |
| or-auto            |                                              0 |                                                       0 |                                                    100 |

## Failure modes (wrong answers by cause, plus counters)

| config             |   wrong result |   nudged |   SQL errors |   repeated SQL |
|:-------------------|---------------:|---------:|-------------:|---------------:|
| claude-opus        |              1 |        0 |            0 |              0 |
| fw-firerouter-opus |              2 |        0 |            5 |              0 |
| glm-flash          |              1 |        3 |            3 |              0 |

## Accuracy % per question

|                    |   claude-opus |   fw-auto |   fw-firerouter-opus |   glm-flash |   or-auto |
|:-------------------|--------------:|----------:|---------------------:|------------:|----------:|
| ('easy', 'c1.1')   |           100 |       100 |                  100 |         100 |       100 |
| ('easy', 'c1.4')   |           100 |       100 |                  100 |         100 |       100 |
| ('easy', 'c1.6')   |           100 |       100 |                  100 |         100 |       100 |
| ('easy', 'c2.1')   |           100 |       100 |                  100 |         100 |       100 |
| ('easy', 'c2.4')   |           100 |       100 |                  100 |         100 |       100 |
| ('easy', 'c2.6')   |           100 |       100 |                  100 |         100 |       100 |
| ('easy', 'c3.1')   |           100 |       100 |                  100 |         100 |       100 |
| ('easy', 'c3.4')   |           100 |       100 |                  100 |         100 |       100 |
| ('easy', 'c3.6')   |           100 |       100 |                  100 |         100 |       100 |
| ('easy', 'c4.1')   |           100 |       100 |                  100 |         100 |       100 |
| ('easy', 'c4.4')   |           100 |       100 |                  100 |         100 |       100 |
| ('easy', 'c4.6')   |           100 |       100 |                  100 |         100 |       100 |
| ('medium', 'c1.2') |           100 |       100 |                  100 |         100 |       100 |
| ('medium', 'c2.2') |           100 |       100 |                  100 |         100 |       100 |
| ('medium', 'c3.2') |           100 |       100 |                  100 |         100 |       100 |
| ('medium', 'c4.2') |           100 |       100 |                  100 |         100 |       100 |
| ('hard', 'c1.3')   |           100 |       100 |                  100 |         100 |       100 |
| ('hard', 'c2.3')   |           100 |       100 |                  100 |         100 |       100 |
| ('hard', 'c3.3')   |           100 |       100 |                  100 |          50 |       100 |
| ('hard', 'c4.3')   |           100 |       100 |                  100 |         100 |       100 |
| ('expert', 'c1.5') |           100 |       100 |                  100 |         100 |       100 |
| ('expert', 'c2.5') |           100 |       100 |                   33 |         100 |       100 |
| ('expert', 'c3.5') |           100 |       100 |                  100 |         100 |       100 |
| ('expert', 'c4.5') |             0 |       100 |                  100 |         100 |       100 |
