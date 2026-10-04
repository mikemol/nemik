# nemik:W121: the Google Tasks sink for nemik-ics (luthen-observability:W234). A host tool, not a
# bazel target: it links the system's KF6 Akonadi, which the hermetic build does not carry.
#   cmake -S tools/akonadi-tasks -B build/akonadi-tasks && cmake --build build/akonadi-tasks
cmake_minimum_required(VERSION 3.20)
project(nemik-akonadi-tasks CXX)
set(CMAKE_CXX_STANDARD 20)
find_package(Qt6 REQUIRED COMPONENTS Core DBus)
find_package(KPim6Akonadi REQUIRED)
find_package(KF6CalendarCore REQUIRED)
add_executable(nemik-akonadi-tasks main.cpp)
target_link_libraries(nemik-akonadi-tasks Qt6::Core Qt6::DBus KPim6::AkonadiCore KF6::CalendarCore)
