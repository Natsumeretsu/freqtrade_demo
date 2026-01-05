# FreqAI 参数表（Parameter table）

这份文档由 Freqtrade 官方页面离线保存后整理为便于“vibe coding 查阅使用”的 Markdown。

- 来源：https://www.freqtrade.io/en/stable/freqai-parameter-table/
- 离线保存时间：Mon Jan 05 2026 11:40:33 GMT+0800 (中国标准时间)

## 0) 本仓库的推荐运行方式（Windows + uv）

本仓库使用 `uv` 管理环境，且仓库根目录就是 Freqtrade 的 `userdir`，建议命令统一写成：

```bash
uv run freqtrade <命令> --userdir "." <参数...>
```

下文若出现 `freqtrade ...` 的官方示例，你可以直接在前面加上 `uv run`，并补上 `--userdir "."`。

---

## 1) 目录速览（H2）

下面列出原文的一级小节标题（H2），便于你快速定位内容：


---

## 2) 原文（自动 Markdown 化，便于搜索与复制）

The table below will list all configuration parameters available for FreqAI. Some of the parameters are exemplified in `config_examples/config_freqai.example.json`.

Mandatory parameters are marked as **Required** and have to be set in one of the suggested ways.

#### General configuration parameters

| Parameter | Description |
| --- | --- |
|  | General configuration parameters within the config.freqai tree |
| freqai | Required. The parent dictionary containing all the parameters for controlling FreqAI. Datatype: Dictionary. |
| train_period_days | Required. Number of days to use for the training data (width of the sliding window). Datatype: Positive integer. |
| backtest_period_days | Required. Number of days to inference from the trained model before sliding the train_period_days window defined above, and retraining the model during backtesting (more info here). This can be fractional days, but beware that the provided timerange will be divided by this number to yield the number of trainings necessary to complete the backtest. Datatype: Float. |
| identifier | Required. A unique ID for the current model. If models are saved to disk, the identifier allows for reloading specific pre-trained models/data. Datatype: String. |
| live_retrain_hours | Frequency of retraining during dry/live runs. Datatype: Float > 0. Default: 0 (models retrain as often as possible). |
| expiration_hours | Avoid making predictions if a model is more than expiration_hours old. Datatype: Positive integer. Default: 0 (models never expire). |
| purge_old_models | Number of models to keep on disk (not relevant to backtesting). Default is 2, which means that dry/live runs will keep the latest 2 models on disk. Setting to 0 keeps all models. This parameter also accepts a boolean to maintain backwards compatibility. Datatype: Integer. Default: 2. |
| save_backtest_models | Save models to disk when running backtesting. Backtesting operates most efficiently by saving the prediction data and reusing them directly for subsequent runs (when you wish to tune entry/exit parameters). Saving backtesting models to disk also allows to use the same model files for starting a dry/live instance with the same model identifier. Datatype: Boolean. Default: False (no models are saved). |
| fit_live_predictions_candles | Number of historical candles to use for computing target (label) statistics from prediction data, instead of from the training dataset (more information can be found here). Datatype: Positive integer. |
| continual_learning | Use the final state of the most recently trained model as starting point for the new model, allowing for incremental learning (more information can be found here). Beware that this is currently a naive approach to incremental learning, and it has a high probability of overfitting/getting stuck in local minima while the market moves away from your model. We have the connections here primarily for experimental purposes and so that it is ready for more mature approaches to continual learning in chaotic systems like the crypto market. Datatype: Boolean. Default: False. |
| write_metrics_to_disk | Collect train timings, inference timings and cpu usage in json file. Datatype: Boolean. Default: False |
| data_kitchen_thread_count | Designate the number of threads you want to use for data processing (outlier methods, normalization, etc.). This has no impact on the number of threads used for training. If user does not set it (default), FreqAI will use max number of threads - 2 (leaving 1 physical core available for Freqtrade bot and FreqUI) Datatype: Positive integer. |
| activate_tensorboard | Indicate whether or not to activate tensorboard for the tensorboard enabled modules (currently Reinforcment Learning, XGBoost, Catboost, and PyTorch). Tensorboard needs Torch installed, which means you will need the torch/RL docker image or you need to answer "yes" to the install question about whether or not you wish to install Torch. Datatype: Boolean. Default: True. |
| wait_for_training_iteration_on_reload | When using /reload or ctrl-c, wait for the current training iteration to finish before completing graceful shutdown. If set to False, FreqAI will break the current training iteration, allowing you to shutdown gracefully more quickly, but you will lose your current training iteration. Datatype: Boolean. Default: True. |

#### Feature parameters

| Parameter | Description |
| --- | --- |
|  | Feature parameters within the freqai.feature_parameters sub dictionary |
| feature_parameters | A dictionary containing the parameters used to engineer the feature set. Details and examples are shown here. Datatype: Dictionary. |
| include_timeframes | A list of timeframes that all indicators in feature_engineering_expand_*() will be created for. The list is added as features to the base indicators dataset. Datatype: List of timeframes (strings). |
| include_corr_pairlist | A list of correlated coins that FreqAI will add as additional features to all pair_whitelist coins. All indicators set in feature_engineering_expand_*() during feature engineering (see details here) will be created for each correlated coin. The correlated coins features are added to the base indicators dataset. Datatype: List of assets (strings). |
| label_period_candles | Number of candles into the future that the labels are created for. This can be used in set_freqai_targets() (see templates/FreqaiExampleStrategy.py for detailed usage). This parameter is not necessarily required, you can create custom labels and choose whether to make use of this parameter or not. Please see templates/FreqaiExampleStrategy.py to see the example usage. Datatype: Positive integer. |
| include_shifted_candles | Add features from previous candles to subsequent candles with the intent of adding historical information. If used, FreqAI will duplicate and shift all features from the include_shifted_candles previous candles so that the information is available for the subsequent candle. Datatype: Positive integer. |
| weight_factor | Weight training data points according to their recency (see details here). Datatype: Positive float (typically < 1). |
| indicator_max_period_candles | No longer used (#7325). Replaced by startup_candle_count which is set in the strategy. startup_candle_count is timeframe independent and defines the maximum period used in feature_engineering_*() for indicator creation. FreqAI uses this parameter together with the maximum timeframe in include_time_frames to calculate how many data points to download such that the first data point does not include a NaN. Datatype: Positive integer. |
| indicator_periods_candles | Time periods to calculate indicators for. The indicators are added to the base indicator dataset. Datatype: List of positive integers. |
| principal_component_analysis | Automatically reduce the dimensionality of the data set using Principal Component Analysis. See details about how it works here Datatype: Boolean. Default: False. |
| plot_feature_importances | Create a feature importance plot for each model for the top/bottom plot_feature_importances number of features. Plot is stored in user_data/models/<identifier>/sub-train-<COIN>_<timestamp>.html. Datatype: Integer. Default: 0. |
| DI_threshold | Activates the use of the Dissimilarity Index for outlier detection when set to > 0. See details about how it works here. Datatype: Positive float (typically < 1). |
| use_SVM_to_remove_outliers | Train a support vector machine to detect and remove outliers from the training dataset, as well as from incoming data points. See details about how it works here. Datatype: Boolean. |
| svm_params | All parameters available in Sklearn's SGDOneClassSVM(). See details about some select parameters here. Datatype: Dictionary. |
| use_DBSCAN_to_remove_outliers | Cluster data using the DBSCAN algorithm to identify and remove outliers from training and prediction data. See details about how it works here. Datatype: Boolean. |
| noise_standard_deviation | If set, FreqAI adds noise to the training features with the aim of preventing overfitting. FreqAI generates random deviates from a gaussian distribution with a standard deviation of noise_standard_deviation and adds them to all data points. noise_standard_deviation should be kept relative to the normalized space, i.e., between -1 and 1. In other words, since data in FreqAI is always normalized to be between -1 and 1, noise_standard_deviation: 0.05 would result in 32% of the data being randomly increased/decreased by more than 2.5% (i.e., the percent of data falling within the first standard deviation). Datatype: Integer. Default: 0. |
| outlier_protection_percentage | Enable to prevent outlier detection methods from discarding too much data. If more than outlier_protection_percentage % of points are detected as outliers by the SVM or DBSCAN, FreqAI will log a warning message and ignore outlier detection, i.e., the original dataset will be kept intact. If the outlier protection is triggered, no predictions will be made based on the training dataset. Datatype: Float. Default: 30. |
| reverse_train_test_order | Split the feature dataset (see below) and use the latest data split for training and test on historical split of the data. This allows the model to be trained up to the most recent data point, while avoiding overfitting. However, you should be careful to understand the unorthodox nature of this parameter before employing it. Datatype: Boolean. Default: False (no reversal). |
| shuffle_after_split | Split the data into train and test sets, and then shuffle both sets individually. Datatype: Boolean. Default: False. |
| buffer_train_data_candles | Cut buffer_train_data_candles off the beginning and end of the training data after the indicators were populated. The main example use is when predicting maxima and minima, the argrelextrema function cannot know the maxima/minima at the edges of the timerange. To improve model accuracy, it is best to compute argrelextrema on the full timerange and then use this function to cut off the edges (buffer) by the kernel. In another case, if the targets are set to a shifted price movement, this buffer is unnecessary because the shifted candles at the end of the timerange will be NaN and FreqAI will automatically cut those off of the training dataset. Datatype: Integer. Default: 0. |

#### Data split parameters

| Parameter | Description |
| --- | --- |
|  | Data split parameters within the freqai.data_split_parameters sub dictionary |
| data_split_parameters | Include any additional parameters available from scikit-learn test_train_split(), which are shown here (external website). Datatype: Dictionary. |
| test_size | The fraction of data that should be used for testing instead of training. Datatype: Positive float < 1. |
| shuffle | Shuffle the training data points during training. Typically, to not remove the chronological order of data in time-series forecasting, this is set to False. Datatype: Boolean. Default: False. |

#### Model training parameters

| Parameter | Description |
| --- | --- |
|  | Model training parameters within the freqai.model_training_parameters sub dictionary |
| model_training_parameters | A flexible dictionary that includes all parameters available by the selected model library. For example, if you use LightGBMRegressor, this dictionary can contain any parameter available by the LightGBMRegressor here (external website). If you select a different model, this dictionary can contain any parameter from that model. A list of the currently available models can be found here. Datatype: Dictionary. |
| n_estimators | The number of boosted trees to fit in the training of the model. Datatype: Integer. |
| learning_rate | Boosting learning rate during training of the model. Datatype: Float. |
| n_jobs, thread_count, task_type | Set the number of threads for parallel processing and the task_type (gpu or cpu). Different model libraries use different parameter names. Datatype: Float. |

#### Reinforcement Learning parameters

| Parameter | Description |
| --- | --- |
|  | Reinforcement Learning Parameters within the freqai.rl_config sub dictionary |
| rl_config | A dictionary containing the control parameters for a Reinforcement Learning model. Datatype: Dictionary. |
| train_cycles | Training time steps will be set based on the `train_cycles * number of training data points. Datatype: Integer. |
| max_trade_duration_candles | Guides the agent training to keep trades below desired length. Example usage shown in prediction_models/ReinforcementLearner.py within the customizable calculate_reward() function. Datatype: int. |
| model_type | Model string from stable_baselines3 or SBcontrib. Available strings include: 'TRPO', 'ARS', 'RecurrentPPO', 'MaskablePPO', 'PPO', 'A2C', 'DQN'. User should ensure that model_training_parameters match those available to the corresponding stable_baselines3 model by visiting their documentation. PPO doc (external website) Datatype: string. |
| policy_type | One of the available policy types from stable_baselines3 Datatype: string. |
| max_training_drawdown_pct | The maximum drawdown that the agent is allowed to experience during training. Datatype: float. Default: 0.8 |
| cpu_count | Number of threads/cpus to dedicate to the Reinforcement Learning training process (depending on if ReinforcementLearner_multiproc is selected or not). Recommended to leave this untouched, by default, this value is set to the total number of physical cores minus 1. Datatype: int. |
| model_reward_parameters | Parameters used inside the customizable calculate_reward() function in ReinforcementLearner.py Datatype: int. |
| add_state_info | Tell FreqAI to include state information in the feature set for training and inferencing. The current state variables include trade duration, current profit, trade position. This is only available in dry/live runs, and is automatically switched to false for backtesting. Datatype: bool. Default: False. |
| net_arch | Network architecture which is well described in stable_baselines3 doc. In summary: [<shared layers>, dict(vf=[<non-shared value network layers>], pi=[<non-shared policy network layers>])]. By default this is set to [128, 128], which defines 2 shared hidden layers with 128 units each. |
| randomize_starting_position | Randomize the starting point of each episode to avoid overfitting. Datatype: bool. Default: False. |
| drop_ohlc_from_features | Do not include the normalized ohlc data in the feature set passed to the agent during training (ohlc will still be used for driving the environment in all cases) Datatype: Boolean. Default: False |
| progress_bar | Display a progress bar with the current progress, elapsed time and estimated remaining time. Datatype: Boolean. Default: False. |

#### PyTorch parameters

##### general

| Parameter | Description |
| --- | --- |
|  | Model training parameters within the freqai.model_training_parameters sub dictionary |
| learning_rate | Learning rate to be passed to the optimizer. Datatype: float. Default: 3e-4. |
| model_kwargs | Parameters to be passed to the model class. Datatype: dict. Default: {}. |
| trainer_kwargs | Parameters to be passed to the trainer class. Datatype: dict. Default: {}. |

##### trainer_kwargs

| Parameter | Description |
| --- | --- |
|  | Model training parameters within the freqai.model_training_parameters.model_kwargs sub dictionary |
| n_epochs | The n_epochs parameter is a crucial setting in the PyTorch training loop that determines the number of times the entire training dataset will be used to update the model's parameters. An epoch represents one full pass through the entire training dataset. Overrides n_steps. Either n_epochs or n_steps must be set. Datatype: int. optional. Default: 10. |
| n_steps | An alternative way of setting n_epochs - the number of training iterations to run. Iteration here refer to the number of times we call optimizer.step(). Ignored if n_epochs is set. A simplified version of the function: n_epochs = n_steps / (n_obs / batch_size) The motivation here is that n_steps is easier to optimize and keep stable across different n_obs - the number of data points. Datatype: int. optional. Default: None. |
| batch_size | The size of the batches to use during training. Datatype: int. Default: 64. |

#### Additional parameters

| Parameter | Description |
| --- | --- |
|  | Extraneous parameters |
| freqai.keras | If the selected model makes use of Keras (typical for TensorFlow-based prediction models), this flag needs to be activated so that the model save/loading follows Keras standards. Datatype: Boolean. Default: False. |
| freqai.conv_width | The width of a neural network input tensor. This replaces the need for shifting candles (include_shifted_candles) by feeding in historical data points as the second dimension of the tensor. Technically, this parameter can also be used for regressors, but it only adds computational overhead and does not change the model training/prediction. Datatype: Integer. Default: 2. |
| freqai.reduce_df_footprint | Recast all numeric columns to float32/int32, with the objective of reducing ram/disk usage and decreasing train/inference timing. This parameter is set in the main level of the Freqtrade configuration file (not inside FreqAI). Datatype: Boolean. Default: False. |
| freqai.override_exchange_check | Override the exchange check to force FreqAI to use exchanges that may not have enough historic data. Turn this to True if you know your FreqAI model and strategy do not require historical data. Datatype: Boolean. Default: False. |

