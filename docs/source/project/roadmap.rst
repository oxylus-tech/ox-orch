Project Roadmap
===============

The project is developped in phases:

- [x] Provide a proof of concept
- [-] Minimum viable product
- [ ] Version 1.0

In order to invest into more advanced tools, we will develop custom application for clients. The goal is to make them open-source once rentabilised in a reasonable way.


0. Proof of concept
-------------------

Proof of concept is there to bring a working example of the overall stack and workflow regarding application development and Oxylus basic layout:

- Assets building and integration;
- User interface and main layout;
- Application example (which is :py:mod:`ox.apps.auth`);
- Propose clean way to take advantage of both frameworks for extensibility;


1. Minimum Viable Product
-------------------------

The minimum viable product phase emphazise on:

- Providing a standard way of application development;
- Quality Assurance:

    - documentation and tests;
    - assets side too;

- Provide basic applications:

    - Contacts: compagnies and contacts management;

- Core:

    - Ensure clean report on errors: HTTP, API validation;
    - Login/logout
    - Settings: system, app, user ones;

It also would introduce:

- CI/CD pipeline into dev process;
- Testing
- Documentation & hosting;
- Packaging:

    - npm and assets packaging;
    - python packaging distribution;
    - ensure installation process is clean and ok;

2. Version 1.0
--------------

Version 1.0 will concentrate on a stable release while providing:

- Applications:

    - Events: base for both agenda and cron;
    - Agenda: provide basic agenda feature;
    - CRON: execute tasks periodically backend-side;

- Ensure all system management tools are okay;
- Ensure the overall system stability;
- Publish packages
