# Results

Runs: 20261005_143531_calib-v3, 20261005_143531_calib-v3-fw

## Accuracy %

| config    |   easy |   medium |   hard |   expert |   all |
|:----------|-------:|---------:|-------:|---------:|------:|
| fw-auto   |    100 |      100 |    100 |      100 |   100 |
| glm-flash |    100 |      100 |     88 |      100 |    98 |

## Cost

| config    |   answers |   correct |   total $ |   LiteLLM-computed $ |   $ / correct answer |   $ / answer |   LLM calls / answer |   LLM seconds / answer |
|:----------|----------:|----------:|----------:|---------------------:|---------------------:|-------------:|---------------------:|-----------------------:|
| fw-auto   |        24 |        24 |     0.082 |                0.082 |               0.0034 |       0.0034 |                  3   |                   10.7 |
| glm-flash |        48 |        47 |     0.052 |                0.052 |               0.0011 |       0.0011 |                  3.5 |                    9.6 |

## Routing threshold: model on each turn's first call, by tier

| config    | easy                          | medium             | hard               | expert             |
|:----------|:------------------------------|:-------------------|:-------------------|:-------------------|
| fw-auto   | glm-5p3 92%, glm-5p3-flash 8% | glm-5p3 100%       | glm-5p3 100%       | glm-5p3 100%       |
| glm-flash | glm-5p3-flash 100%            | glm-5p3-flash 100% | glm-5p3-flash 100% | glm-5p3-flash 100% |

## Routing behaviour

| config    |   answers with a switch inside the tool loop % |   conversations whose turns start on different models % |   turns that start on the same model in every repeat % |
|:----------|-----------------------------------------------:|--------------------------------------------------------:|-------------------------------------------------------:|
| fw-auto   |                                              0 |                                                      25 |                                                    100 |
| glm-flash |                                              0 |                                                       0 |                                                    100 |

## Failure modes (wrong answers by cause, plus counters)

| config    |   wrong result |   nudged |   SQL errors |   repeated SQL |
|:----------|---------------:|---------:|-------------:|---------------:|
| glm-flash |              1 |        3 |            3 |              0 |

## Accuracy % per question

|                    |   fw-auto |   glm-flash |
|:-------------------|----------:|------------:|
| ('easy', 'c1.1')   |       100 |         100 |
| ('easy', 'c1.4')   |       100 |         100 |
| ('easy', 'c1.6')   |       100 |         100 |
| ('easy', 'c2.1')   |       100 |         100 |
| ('easy', 'c2.4')   |       100 |         100 |
| ('easy', 'c2.6')   |       100 |         100 |
| ('easy', 'c3.1')   |       100 |         100 |
| ('easy', 'c3.4')   |       100 |         100 |
| ('easy', 'c3.6')   |       100 |         100 |
| ('easy', 'c4.1')   |       100 |         100 |
| ('easy', 'c4.4')   |       100 |         100 |
| ('easy', 'c4.6')   |       100 |         100 |
| ('medium', 'c1.2') |       100 |         100 |
| ('medium', 'c2.2') |       100 |         100 |
| ('medium', 'c3.2') |       100 |         100 |
| ('medium', 'c4.2') |       100 |         100 |
| ('hard', 'c1.3')   |       100 |         100 |
| ('hard', 'c2.3')   |       100 |         100 |
| ('hard', 'c3.3')   |       100 |          50 |
| ('hard', 'c4.3')   |       100 |         100 |
| ('expert', 'c1.5') |       100 |         100 |
| ('expert', 'c2.5') |       100 |         100 |
| ('expert', 'c3.5') |       100 |         100 |
| ('expert', 'c4.5') |       100 |         100 |
