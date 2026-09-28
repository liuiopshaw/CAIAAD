"""
ECOMATS text definitions (English).

TEXTS is the single data source for all UI texts, agent role/goal descriptions,
task descriptions and prompt prefixes, retrieved via get_text() in
src/locales/__init__.py. The project is English-only (the zh locale was removed);
TEXTS keeps the "en" top-level key for backward compatibility with existing
callers.
"""

# Three-level key structure: language code -> category -> key -> field
# Categories:
#   - agents: agent role names and goal descriptions
#   - tasks: task descriptions and expected outputs
#   - ui: user-interface texts (welcome, input prompts, menu options)

TEXTS = {"en": {'agents': {'material_designer': {'role': 'Material Design Expert',
                                  'goal': 'Design and optimize water treatment material solutions, '
                                          'strictly following material type classification and '
                                          'structural description specifications',
                                  'backstory_suffix': '\n'
                                                      'When outputting design results, include the '
                                                      'following detailed information:\n'
                                                      '- Materials Project ID (mp-xxx) (if the '
                                                      'material exists in the database)\n'
                                                      '- Chemical formula and crystal structure '
                                                      'description\n'
                                                      '- Key physical properties (e.g., band gap, '
                                                      'density)\n'
                                                      '- Thermodynamic stability (height on energy '
                                                      'convex hull)\n'
                                                      '\n'
                                                      'Tool usage strategy (rate limiting and '
                                                      'reuse):\n'
                                                      '- Prioritize reusing previously obtained '
                                                      'structure validation or material identifier '
                                                      'results\n'
                                                      '- Only call Materials Project search when '
                                                      'necessary information is missing, using '
                                                      'minimal field sets\n'
                                                      '- Limit element combination queries to '
                                                      'avoid large-scale data retrieval\n'},
            'expert_a': {'role': 'Advanced Oxidation Assessment Expert A',
                         'goal': 'Evaluate the feasibility and superiority of material design '
                                 'solutions from catalytic activity and reaction mechanism '
                                 'perspectives'},
            'expert_b': {'role': 'Advanced Oxidation Assessment Expert B',
                         'goal': 'Evaluate material design solutions from stability and durability '
                                 'perspectives'},
            'expert_c': {'role': 'Advanced Oxidation Assessment Expert C',
                         'goal': 'Evaluate material design solutions from environmental safety and '
                                 'sustainability perspectives'},
            'final_validator': {'role': 'Final Validation Expert',
                                'goal': 'Integrate multiple expert evaluations to conduct final '
                                        'review and validation of material design solutions'},
            'mechanism_expert': {'role': 'Reaction Mechanism Analysis Expert',
                                 'goal': 'Conduct in-depth analysis of catalytic reaction '
                                         'mechanisms in water treatment processes'},
            'synthesis_expert': {'role': 'Synthesis Method Guidance Expert',
                                 'goal': 'Provide detailed and feasible synthesis methods and '
                                         'process parameters for designed materials'},
            'operation_expert': {'role': 'Operation Parameter Suggestion Expert',
                                 'goal': 'Provide optimal operation parameters and usage '
                                         'recommendations based on material properties and '
                                         'application scenarios'},
            'coordinator': {'role': 'Task Coordination Expert',
                            'goal': 'Coordinate and distribute tasks among agents to ensure '
                                    'efficient workflow'}},
 'tasks': {'design_task': {'description': 'Design water treatment material solutions based on user '
                                          'requirements.\n'
                                          '\n'
                                          'Design Steps:\n'
                                          '1. Analyze target pollutant characteristics and '
                                          'treatment requirements\n'
                                          '2. Select appropriate material types (e.g., single-atom '
                                          'catalysts, dual-atom catalysts, MOF materials)\n'
                                          '3. Prioritize reusing previously obtained structure '
                                          'validation or identifier results; only call Materials '
                                          'Project minimal field search when necessary\n'
                                          '4. **Mandatory: Use PubChem tool to verify target '
                                          'pollutant chemical information**\n'
                                          '5. Design material structure based on tool data\n'
                                          '6. **Mandatory: Use Structure Validator tool to verify '
                                          'if designed material structures actually exist**\n'
                                          '7. Redesign if validation fails\n'
                                          '8. Optimize material structure parameters to ensure '
                                          'catalytic performance and stability\n'
                                          '9. Balance material diversity, structural stability, '
                                          'and catalytic performance\n'
                                          '\n'
                                          'Material Type Classification Requirements:\n'
                                          '1. **Pure Metals**: Elemental metals, alloys, '
                                          'nanoparticles\n'
                                          '2. **Metal Oxides**: Single oxides, composite oxides, '
                                          'layered double hydroxides\n'
                                          '3. **Metal Sulfides**: Transition metal sulfides and '
                                          'composites\n'
                                          '4. **Metal Nitrides/Carbides**: Various metal nitrides '
                                          'and carbides\n'
                                          '5. **MOF/COF Materials**: Traditional and '
                                          'functionalized framework materials\n'
                                          '6. **Carbon-based Materials**: Graphene, carbon '
                                          'nanotubes, porous carbon, etc.\n'
                                          '7. **Single-atom Catalysts**: Single-atom, dual-atom, '
                                          'multi-atom cluster catalysts\n'
                                          '8. **Composite Materials**: Multi-material composite '
                                          'systems\n'
                                          '9. **Bio-based Materials**: Enzyme catalysts and '
                                          'biopolymer-based materials\n'
                                          '\n'
                                          'Design Key Points:\n'
                                          '- Ensure materials have good catalytic performance and '
                                          'structural stability\n'
                                          '- Optimize active sites and reaction pathways\n'
                                          '- Meet target pollutant degradation requirements\n'
                                          '- **Must verify if designed material structures exist '
                                          'in reality**\n',
                           'expected_output': 'Complete material design solution including:\n'
                                              '1. Material composition (material type and key '
                                              'structural parameters)\n'
                                              '2. Design principle explanation\n'
                                              '3. Stability assurance measures\n'
                                              '4. Expected catalytic performance\n'
                                              '5. Detailed structure description (following '
                                              'material type and structure requirements)\n'
                                              '6. Synthesis feasibility assessment\n'},
           'evaluation_task': {'description': 'Professionally evaluate the material design '
                                              'solution.\n'
                                              '\n'
                                              'Evaluation Dimensions:\n'
                                              '1. Catalytic activity and reaction efficiency\n'
                                              '2. Structural stability and durability\n'
                                              '3. Environmental safety and sustainability\n'
                                              '4. Cost-benefit analysis\n'
                                              '5. Industrial feasibility\n'
                                              '\n'
                                              'Evaluation Requirements:\n'
                                              '- Provide specific scores and detailed evaluation '
                                              'opinions\n'
                                              '- Identify advantages and disadvantages of the '
                                              'design\n'
                                              '- Provide improvement suggestions\n',
                               'expected_output': 'Expert evaluation report including:\n'
                                                  '1. Scores for each evaluation dimension (1-10)\n'
                                                  '2. Detailed evaluation opinions\n'
                                                  '3. Advantages and disadvantages of the design\n'
                                                  '4. Specific improvement suggestions\n'},
           'final_validation_task': {'description': 'Integrate multiple expert evaluations for '
                                                    'final validation of the material design '
                                                    'solution.\n'
                                                    '\n'
                                                    'Validation Content:\n'
                                                    '1. Summarize expert evaluations\n'
                                                    '2. Analyze consistency and divergence of '
                                                    'evaluation results\n'
                                                    '3. Provide final validation conclusions\n'
                                                    '4. Select optimal design solutions\n',
                                     'expected_output': 'Final validation report including:\n'
                                                        '1. Expert evaluation summary\n'
                                                        '2. Final validation conclusions\n'
                                                        '3. Recommended optimal design solutions '
                                                        'with ranking\n'
                                                        '4. Comprehensive improvement '
                                                        'suggestions\n'},
           'mechanism_analysis_task': {'description': 'Conduct in-depth analysis of catalytic '
                                                      'reaction mechanisms in water treatment.\n'
                                                      '\n'
                                                      'Analysis Content:\n'
                                                      '1. Reactive site analysis\n'
                                                      '2. Reaction pathways and intermediates\n'
                                                      '3. Electron transfer mechanisms\n'
                                                      '4. Free radical generation mechanisms\n'
                                                      '5. Pollutant degradation pathways\n',
                                       'expected_output': 'Reaction mechanism analysis report '
                                                          'including:\n'
                                                          '1. Detailed active site description\n'
                                                          '2. Complete reaction pathway diagram\n'
                                                          '3. Key intermediate analysis\n'
                                                          '4. Electron transfer mechanism '
                                                          'explanation\n'
                                                          '5. Degradation efficiency prediction\n'},
           'synthesis_method_task': {'description': 'Provide detailed and feasible synthesis '
                                                    'methods for designed materials.\n'
                                                    '\n'
                                                    '**IMPORTANT**: Determine the number of '
                                                    'synthesis methods based on user request:\n'
                                                    '- If user requests "N synthesis methods", '
                                                    'provide exactly N different methods\n'
                                                    '- If user requests "multiple"/"several" '
                                                    'methods, provide at least 3 different '
                                                    'methods\n'
                                                    '- If no quantity specified, provide 1 optimal '
                                                    'method\n'
                                                    '\n'
                                                    'Synthesis Plan Requirements:\n'
                                                    '1. Detailed synthesis steps\n'
                                                    '2. Required raw materials and reagent list\n'
                                                    '3. Reaction conditions and parameters\n'
                                                    '4. Key process control points\n'
                                                    '5. Quality testing methods\n',
                                     'expected_output': 'Synthesis method guide including:\n'
                                                        '1. Exact number of synthesis methods '
                                                        'requested by user (MUST match)\n'
                                                        '2. Complete synthesis process for each '
                                                        'method\n'
                                                        '3. Detailed operation steps\n'
                                                        '4. Raw materials and reagent list\n'
                                                        '5. Process parameter table\n'
                                                        '6. Quality control standards\n'},
           'operation_suggesting_task': {'description': 'Provide optimal operation parameter '
                                                        'recommendations based on material '
                                                        'properties and application scenarios.\n'
                                                        '\n'
                                                        'Recommendation Content:\n'
                                                        '1. Optimal operating conditions (pH, '
                                                        'temperature, concentration, etc.)\n'
                                                        '2. Catalyst dosage optimization\n'
                                                        '3. Reaction time control\n'
                                                        '4. Operation precautions\n'
                                                        '5. Safety protection measures\n',
                                         'expected_output': 'Operation parameter recommendation '
                                                            'including:\n'
                                                            '1. Optimal operating conditions '
                                                            'table\n'
                                                            '2. Parameter optimization '
                                                            'suggestions\n'
                                                            '3. Operating procedures\n'
                                                            '4. Safety precautions\n'
                                                            '5. Performance maintenance guide\n'}},
 'ui': {'welcome': 'Welcome to ECOMATS - Multi-Agent System for Water Treatment Material Design',
        'input_prompt': 'Please enter your material design requirements:',
        'example': 'Example: Design an efficient catalyst for treating wastewater containing heavy '
                   'metal cadmium',
        'select_mode': 'Please select workflow mode:',
        'preset_sync': 'Preset Workflow (Sync)',
        'preset_async': 'Preset Workflow (Async) ⚡ Recommended!',
        'autonomous_sync': 'Autonomous Agent Scheduling (Sync)',
        'autonomous_async': 'Autonomous Agent Scheduling (Async) ⚡ Recommended!',
        'execution_complete': 'Execution Complete!',
        'result_saved': 'Result saved to'}}}
