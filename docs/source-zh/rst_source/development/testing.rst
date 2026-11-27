测试与 CI
=========

GitHub 自动运行 CPU 单元测试，并在日志中输出代码行覆盖率。非草稿 PR 贴上 ``run-ci`` 标签或提交合入 ``main`` 时，**Simulator CI** 会根据改动路径自动选择对应的 GPU 端到端套件，通过 ``rpent-install.sh`` 在干净虚拟环境中完成安装校验并运行测试。例如：修改 RLDX 会触发 RoboCasa，修改共享规划器会触发全部七个套件，只改文档则跳过仿真测试。

每个 GPU 套件都会通过公开 CLI 依次调用当前环境暴露的全部工具并最终调用 ``finish``。


测试结构
--------

``tests/`` 包含三个顶层目录：

.. list-table::
   :header-rows: 1
   :widths: 26 74

   * - 目录
     - 职责
   * - ``tests/unit_tests/``
     - 离线 CPU 单元测试，无需 GPU、仿真器或模型权重。不启动真实服务，使用轻量级内存替代实现验证接口、配置解析、数据格式转换与进程清理。
   * - ``tests/tooling/``
     - 独立检查脚本，无需安装 Python 环境即可运行，用于校验目录结构、``component.toml`` 依赖清单与模块导入边界。
   * - ``tests/e2e_tests/``
     - 声明式 GPU 端到端测试套件（``suites/*.toml``）与通用运行脚本（``run_gpu_suite.sh``），通过公开 CLI 依次覆盖当前环境暴露的全部工具。

单元测试目录与源码目录保持对应：

.. list-table::
   :header-rows: 1
   :widths: 36 64

   * - 源码目录
     - 单元测试目录
   * - ``rpent/<module>``
     - ``tests/unit_tests/rpent/<module>/``
   * - ``robots/<name>/``
     - ``tests/unit_tests/robots/<name>/``
   * - ``components/models/<name>/``
     - ``tests/unit_tests/components/models/``
   * - ``components/tools/<name>/``
     - ``tests/unit_tests/components/tools/``
   * - ``component.toml`` 依赖清单
     - 由 ``tests/unit_tests/installs/`` 与 ``./tests/tooling/run.sh layout`` 自动校验

编写测试时遵循以下约定：

- 仅单个测试文件用到的辅助类与准备逻辑保留在当前测试文件内；多个测试文件共用的初始化逻辑再移至 ``conftest.py``。
- 测试文件按验证重点命名：``*_contracts.py`` 验证接口与配置，``*_loopback.py`` 验证本地端口或 HTTP 通信，``*_lifecycle.py`` 验证服务启停与清理，``*_smoke.py`` 验证基础启动流程。
- ``tests/unit_tests/rpent/install/`` 使用临时目录验证安装器自身逻辑；针对仓库内真实 ``component.toml`` 清单的校验放在 ``tests/unit_tests/installs/``。

新增机器人或模型所需测试
------------------------

接入新机器人或仿真环境
~~~~~~~~~~~~~~~~~~~~~~

在 ``robots/<name>/`` 下新增机器人（或同时在 ``components/sim/<name>/`` 下新增仿真器）时，需补充以下两部分：

1. **离线 CPU 单元测试**\ （位于 ``tests/unit_tests/robots/<name>/``）：

   - 验证机器人注册、CLI 参数、配置解析、Prompt 组装与工具定义。
   - 使用轻量级本地测试服务替代真实仿真器与模型，验证 CLI 执行、本地 RPC 通信与子进程正常退出。
   - 运行 ``./tests/tooling/run.sh layout`` 与 ``tests/unit_tests/installs/``，确认 ``component.toml`` 与导入边界通过校验。

2. **GPU 端到端套件**\ （新增 ``tests/e2e_tests/suites/<name>.toml``，参考同目录的 ``robocasa.toml`` 或 ``libero.toml``）：

   CI 会自动发现 ``suites/*.toml``，无需修改脚本或工作流：

   - 填写 ``component`` 指定安装组件，并在 ``[[cases]]`` 中为每个动作模型后端写一条用例（共用参数和环境变量放 ``base_args`` / ``env``）。
   - 资产、权重和解释器直接写 ``assets/...``、``models/...``、``venvs/...`` 相对路径，卡号用 ``{gpu}`` 占位；路径缺失时自动跳过该用例。
   - 推荐填 ``action_tool`` 与 ``action_count_field`` 验证动作真正执行；有特殊安装收尾或独立服务需求时，再按需补充 ``[setup]`` 或 ``[cases.sidecar]``。

完整的机器人接入步骤见 :doc:`add_robot`。

接入新模型
~~~~~~~~~~

在 ``components/models/<name>/`` 下新增动作模型或感知模型时，需补充以下两部分：

1. **离线 CPU 单元测试**\ （位于 ``tests/unit_tests/components/models/``，特定机器人的适配逻辑位于 ``tests/unit_tests/robots/<robot>/``）：

   - 验证配置校验、启动参数检查，以及 RPent 物理量与模型输入输出之间的格式转换。
   - 使用轻量级测试后端验证本地 HTTP/socket 通信，包括多会话隔离、reset、错误处理与 worker 正常退出。

2. **GPU 端到端用例**\ （加入对应机器人的 ``tests/e2e_tests/suites/<robot>.toml``）：

   - 新增一条 ``[[cases]]``，填写该后端的 CLI 参数与共享目录下的资源相对路径。
   - 缺少权重、解释器或 endpoint 时会自动跳过对应用例，不影响同套件内其他用例。

完整的动作模型接入步骤见 :doc:`add_action_model`。

本地运行测试
------------

本地运行离线测试
~~~~~~~~~~~~~~~~

安装 ``infra-unit_cpu``\ （包含模型服务单元测试所需的 CPU 版 PyTorch），再运行 pytest：

.. code-block:: bash

   ./rpent-install.sh install infra-unit_cpu --venv .venv-unit-cpu
   .venv-unit-cpu/bin/python -m pytest tests/unit_tests -v
   .venv-unit-cpu/bin/python -m pytest tests/unit_tests/robots/<name> -v

仓库结构检查无需激活虚拟环境，直接执行：

.. code-block:: bash

   ./tests/tooling/run.sh layout

本地运行 GPU 套件
~~~~~~~~~~~~~~~~~

在具备独立 NVIDIA GPU、EGL 以及对应资产和权重的机器上，传入两个不存在的输出目录与虚拟环境目录运行单个套件：

.. code-block:: bash

   export CUDA_VISIBLE_DEVICES=<单个物理 GPU 编号>
   export MUJOCO_GL=egl
   export PYOPENGL_PLATFORM=egl

   bash tests/e2e_tests/run_gpu_suite.sh \
     <target> \
     /path/to/new-output-dir \
     /path/to/new-venv-root

在已安装环境的机器上调试单个套件或用例时，可直接运行 ``RPENT_E2E_SUITE=<target> pytest tests/e2e_tests/test_suites.py -v -k <expression>``。
