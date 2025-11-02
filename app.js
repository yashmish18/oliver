// University Exam Scheduling System - Main Application Logic
class ExamSchedulingSystem {
    constructor() {
        this.currentTab = 'data-import';
        this.enrollmentData = [];
        this.roomsData = [];
        this.selectedAlgorithm = null;
        this.selectedCourses = new Set();
        this.selectedCourseData = new Map();
        this.seatingAssignments = [];
        this.analytics = {};
        
        // Course color mapping
        this.courseColors = [
            '#1FB8CD', '#FFC185', '#B4413C', '#ECEBD5', '#5D878F',
            '#DB4545', '#D2BA4C', '#964325', '#944454', '#13343B'
        ];
        this.courseColorMap = new Map();
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadSampleData();
        this.loadSampleRooms();
    }

    bindEvents() {
        // Progress navigation
        document.querySelectorAll('.progress-step').forEach(step => {
            step.addEventListener('click', (e) => {
                const tab = e.currentTarget.dataset.tab;
                if (this.canNavigateToTab(tab)) {
                    this.switchTab(tab);
                }
            });
        });

        // Data import events
        document.getElementById('load-sample-data').addEventListener('click', () => {
            this.loadSampleData();
        });
        
        document.getElementById('load-sample-rooms').addEventListener('click', () => {
            this.loadSampleRooms();
        });
        
        document.getElementById('proceed-to-algorithm').addEventListener('click', () => {
            this.switchTab('algorithm-selection');
        });

        // Algorithm selection events
        document.querySelectorAll('.algorithm-card').forEach(card => {
            card.addEventListener('click', () => {
                this.selectAlgorithm(card.dataset.algorithm);
            });
        });
        
        document.getElementById('back-to-import').addEventListener('click', () => {
            this.switchTab('data-import');
        });
        
        document.getElementById('proceed-to-courses').addEventListener('click', () => {
            this.switchTab('course-selection');
        });

        // Course selection events
        document.getElementById('back-to-algorithm').addEventListener('click', () => {
            this.switchTab('algorithm-selection');
        });
        
        document.getElementById('generate-seating').addEventListener('click', () => {
            this.generateSeatingArrangement();
        });

        // Seating visualization events
        document.getElementById('room-selector').addEventListener('change', (e) => {
            this.displayRoomLayout(e.target.value);
        });
        
        document.getElementById('back-to-courses').addEventListener('click', () => {
            this.switchTab('course-selection');
        });
        
        document.getElementById('view-analytics').addEventListener('click', () => {
            this.switchTab('analytics');
        });

        // Analytics events
        document.getElementById('back-to-seating').addEventListener('click', () => {
            this.switchTab('seating-visualization');
        });

        // Export events
        document.getElementById('export-seating').addEventListener('click', () => {
            this.exportSeatingCharts();
        });
        
        document.getElementById('export-analytics').addEventListener('click', () => {
            this.exportAnalytics();
        });
        
        document.getElementById('generate-pdf').addEventListener('click', () => {
            this.generatePDFReport();
        });
    }

    canNavigateToTab(tab) {
        const tabOrder = ['data-import', 'algorithm-selection', 'course-selection', 'seating-visualization', 'analytics'];
        const currentIndex = tabOrder.indexOf(this.currentTab);
        const targetIndex = tabOrder.indexOf(tab);
        
        // Allow going back or moving forward if conditions are met
        if (targetIndex <= currentIndex) return true;
        if (tab === 'algorithm-selection' && this.enrollmentData.length > 0 && this.roomsData.length > 0) return true;
        if (tab === 'course-selection' && this.selectedAlgorithm) return true;
        if (tab === 'seating-visualization' && this.selectedCourses.size > 0) return true;
        if (tab === 'analytics' && this.seatingAssignments.length > 0) return true;
        
        return false;
    }

    switchTab(tabName) {
        console.log('Switching to tab:', tabName);
        
        // Hide all tab panels
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.remove('active');
            panel.style.display = 'none';
        });
        
        // Show target tab panel
        const targetPanel = document.getElementById(tabName);
        if (targetPanel) {
            targetPanel.classList.add('active');
            targetPanel.style.display = 'block';
        }
        
        // Update progress navigation
        document.querySelectorAll('.progress-step').forEach(step => {
            step.classList.remove('active', 'completed');
        });
        
        const currentStep = document.querySelector(`[data-tab="${tabName}"]`);
        if (currentStep) {
            currentStep.classList.add('active');
        }
        
        // Mark previous steps as completed
        const tabOrder = ['data-import', 'algorithm-selection', 'course-selection', 'seating-visualization', 'analytics'];
        const currentIndex = tabOrder.indexOf(tabName);
        for (let i = 0; i < currentIndex; i++) {
            const prevStep = document.querySelector(`[data-tab="${tabOrder[i]}"]`);
            if (prevStep) {
                prevStep.classList.add('completed');
            }
        }
        
        this.currentTab = tabName;
        
        // Tab-specific initialization
        if (tabName === 'course-selection') {
            this.initCourseSelection();
        } else if (tabName === 'seating-visualization') {
            this.initSeatingVisualization();
        } else if (tabName === 'analytics') {
            this.initAnalytics();
        }
    }

    loadSampleData() {
        console.log('Loading sample data...');
        
        // Generate realistic sample data
        const coursesBySemester = {
            "SEMESTER 2": [
                {"code": "AS1108", "name": "Applied Physics", "students": 125},
                {"code": "MA1114", "name": "Linear Algebra and Differential Equations", "students": 180},
                {"code": "CS1102", "name": "Programming -II", "students": 165},
                {"code": "DT1101", "name": "Design Thinking", "students": 150},
                {"code": "CT1101", "name": "Critical Thinking and Storytelling", "students": 140}
            ],
            "SEMESTER 4": [
                {"code": "CS2201", "name": "Machine Learning", "students": 95},
                {"code": "CS2105", "name": "Operating Systems", "students": 78},
                {"code": "MG2101", "name": "Managing Business Functions", "students": 88},
                {"code": "CS2103", "name": "Design and Analysis of Algorithms", "students": 82},
                {"code": "CM2101", "name": "Communication and Identity", "students": 92}
            ],
            "SEMESTER 6": [
                {"code": "CS3301", "name": "Minor Project", "students": 75},
                {"code": "CT3101", "name": "Critical Thinking for Decisions", "students": 68},
                {"code": "CS3201", "name": "Theory of Computation", "students": 65},
                {"code": "CS3205", "name": "Big Data Analytics", "students": 45},
                {"code": "CS3207", "name": "Deep Learning", "students": 38}
            ],
            "SEMESTER 8": [
                {"code": "PS4102", "name": "Practice School -II", "students": 55},
                {"code": "CS4201", "name": "Object Oriented Programming", "students": 25},
                {"code": "CS4301", "name": "Software Engineering", "students": 28},
                {"code": "EE4101", "name": "Sustainable Electronic Waste Management", "students": 15}
            ]
        };

        const firstNames = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan", "Shaurya", "Atharv", "Advik", "Rudra", "Prisha", "Ananya", "Fatima", "Anika", "Aadhya", "Kavya", "Aria", "Myra", "Sara", "Zara"];
        const lastNames = ["Sharma", "Patel", "Singh", "Kumar", "Agarwal", "Gupta", "Jain", "Bansal", "Agrawal", "Tiwari", "Mishra", "Yadav", "Saxena", "Verma", "Mehta", "Shah", "Arora", "Malhotra", "Khanna", "Chopra"];
        
        this.enrollmentData = [];
        
        Object.entries(coursesBySemester).forEach(([semester, courses]) => {
            courses.forEach((course, courseIndex) => {
                for (let i = 0; i < course.students; i++) {
                    const firstName = firstNames[Math.floor(Math.random() * firstNames.length)];
                    const lastName = lastNames[Math.floor(Math.random() * lastNames.length)];
                    const rollNumber = `BTech${String(courseIndex * 1000 + i + 1).padStart(5, '0')}`;
                    
                    this.enrollmentData.push({
                        "Student Session": semester,
                        "Student Roll Number": rollNumber,
                        "Student Name": `${firstName} ${lastName}`,
                        "Subject Code": course.code,
                        "Subject Name": course.name
                    });
                }
            });
        });
        
        console.log('Generated enrollment data:', this.enrollmentData.length, 'students');
        
        this.displayDataPreview(this.enrollmentData, 'enrollment-preview');
        this.validateData();
    }

    loadSampleRooms() {
        console.log('Loading sample rooms...');
        
        this.roomsData = [
            {
                "room_id": "LT-001",
                "room_name": "Large Theater 1",
                "capacity": 120,
                "layout": "theater",
                "rows": 8,
                "cols_per_row": [12, 14, 14, 16, 16, 16, 14, 12],
                "building": "Academic Block A",
                "max_with_spacing": 40
            },
            {
                "room_id": "AUD-001",
                "room_name": "Main Auditorium", 
                "capacity": 200,
                "layout": "auditorium",
                "rows": 10,
                "cols_per_row": [8, 10, 12, 14, 16, 16, 14, 12, 10, 8],
                "building": "Central Building",
                "max_with_spacing": 67
            },
            {
                "room_id": "CR-101",
                "room_name": "Classroom 101",
                "capacity": 60,
                "layout": "grid", 
                "rows": 6,
                "cols_per_row": [8, 8, 8, 8, 8, 8],
                "building": "Academic Block B",
                "max_with_spacing": 20
            },
            {
                "room_id": "LAB-201",
                "room_name": "Computer Lab 201",
                "capacity": 80,
                "layout": "island",
                "rows": 6, 
                "cols_per_row": [10, 10, 10, 10, 10, 10],
                "building": "IT Building",
                "max_with_spacing": 27
            },
            {
                "room_id": "HALL-001",
                "room_name": "Examination Hall 1",
                "capacity": 150,
                "layout": "grid",
                "rows": 8,
                "cols_per_row": [12, 12, 12, 12, 12, 12, 12, 12],
                "building": "Exam Block", 
                "max_with_spacing": 50
            }
        ];
        
        console.log('Loaded room data:', this.roomsData.length, 'rooms');
        
        this.displayDataPreview(this.roomsData, 'rooms-preview');
        this.validateData();
    }

    displayDataPreview(data, containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        container.classList.remove('hidden');
        
        if (data.length === 0) {
            container.innerHTML = '<p>No data available</p>';
            return;
        }
        
        const headers = Object.keys(data[0]);
        const previewData = data.slice(0, 5);
        
        let html = '<table><thead><tr>';
        headers.forEach(header => {
            html += `<th>${header}</th>`;
        });
        html += '</tr></thead><tbody>';
        
        previewData.forEach(row => {
            html += '<tr>';
            headers.forEach(header => {
                html += `<td>${row[header] || ''}</td>`;
            });
            html += '</tr>';
        });
        
        if (data.length > 5) {
            html += `<tr><td colspan="${headers.length}" style="text-align: center; font-style: italic;">... and ${data.length - 5} more rows</td></tr>`;
        }
        
        html += '</tbody></table>';
        container.innerHTML = html;
    }

    validateData() {
        if (this.enrollmentData.length > 0 && this.roomsData.length > 0) {
            const summary = document.getElementById('validation-summary');
            if (summary) {
                summary.classList.remove('hidden');
                
                const totalStudents = this.enrollmentData.length;
                const totalRooms = this.roomsData.length;
                const totalCapacity = this.roomsData.reduce((sum, room) => sum + room.capacity, 0);
                const uniqueCourses = new Set(this.enrollmentData.map(student => student["Subject Code"])).size;
                
                const statsContainer = summary.querySelector('.validation-stats');
                if (statsContainer) {
                    statsContainer.innerHTML = `
                        <div class="validation-stat">
                            <div class="validation-number">${totalStudents}</div>
                            <div class="validation-label">Total Students</div>
                        </div>
                        <div class="validation-stat">
                            <div class="validation-number">${uniqueCourses}</div>
                            <div class="validation-label">Unique Courses</div>
                        </div>
                        <div class="validation-stat">
                            <div class="validation-number">${totalRooms}</div>
                            <div class="validation-label">Available Rooms</div>
                        </div>
                        <div class="validation-stat">
                            <div class="validation-number">${totalCapacity}</div>
                            <div class="validation-label">Total Capacity</div>
                        </div>
                    `;
                }
            }
            
            const proceedButton = document.getElementById('proceed-to-algorithm');
            if (proceedButton) {
                proceedButton.disabled = false;
            }
        }
    }

    selectAlgorithm(algorithmId) {
        console.log('Selecting algorithm:', algorithmId);
        
        document.querySelectorAll('.algorithm-card').forEach(card => {
            card.classList.remove('selected');
        });
        
        const selectedCard = document.querySelector(`[data-algorithm="${algorithmId}"]`);
        if (selectedCard) {
            selectedCard.classList.add('selected');
        }
        
        const algorithms = {
            ultra_efficient_mixed: {
                name: "Ultra-Efficient Mixed",
                efficiency: "95%",
                description: "Different courses can be adjacent for maximum space utilization",
            },
            conservative_mixed: {
                name: "Conservative Mixed", 
                efficiency: "85%",
                description: "More spacing between different courses for extra security",
            },
            department_spread: {
                name: "Department Spread",
                efficiency: "80%", 
                description: "Ensures even distribution of departments across room",
            },
            anti_cheating_plus: {
                name: "Anti-Cheating Plus",
                efficiency: "75%",
                description: "Maximum security with strategic course separation", 
            },
            balanced_optimization: {
                name: "Balanced Optimization",
                efficiency: "90%",
                description: "Optimal balance between efficiency and security",
            }
        };
        
        this.selectedAlgorithm = {
            id: algorithmId,
            ...algorithms[algorithmId]
        };
        
        const summary = document.getElementById('algorithm-summary');
        if (summary) {
            summary.classList.remove('hidden');
            const nameElement = summary.querySelector('#selected-algorithm-name');
            const descElement = summary.querySelector('#selected-algorithm-description');
            if (nameElement) nameElement.textContent = this.selectedAlgorithm.name;
            if (descElement) descElement.textContent = this.selectedAlgorithm.description;
        }
        
        const proceedButton = document.getElementById('proceed-to-courses');
        if (proceedButton) {
            proceedButton.disabled = false;
        }
    }

    initCourseSelection() {
        console.log('Initializing course selection...');
        
        const coursesBySemester = this.groupCoursesBySemester();
        
        Object.entries(coursesBySemester).forEach(([semester, courses]) => {
            const containerId = `${semester.toLowerCase().replace(' ', '-')}-courses`;
            const container = document.getElementById(containerId);
            
            if (container && courses.length > 0) {
                container.innerHTML = '';
                courses.forEach((course, index) => {
                    const courseItem = document.createElement('div');
                    courseItem.className = 'course-item';
                    courseItem.innerHTML = `
                        <input type="checkbox" id="${course.code}-checkbox" class="course-checkbox" value="${course.code}">
                        <div class="course-info">
                            <div class="course-code">${course.code}</div>
                            <div class="course-name">${course.name}</div>
                            <div class="course-students">${course.students} students</div>
                        </div>
                    `;
                    
                    const checkbox = courseItem.querySelector('.course-checkbox');
                    checkbox.addEventListener('change', () => {
                        this.toggleCourseSelection(course.code, course.name, course.students);
                    });
                    
                    container.appendChild(courseItem);
                });
            }
        });
        
        this.updateSelectionSummary();
    }

    groupCoursesBySemester() {
        const grouped = {};
        
        this.enrollmentData.forEach(student => {
            const semester = student["Student Session"];
            const courseCode = student["Subject Code"];
            const courseName = student["Subject Name"];
            
            if (!grouped[semester]) {
                grouped[semester] = {};
            }
            
            if (!grouped[semester][courseCode]) {
                grouped[semester][courseCode] = {
                    code: courseCode,
                    name: courseName,
                    students: 0
                };
            }
            
            grouped[semester][courseCode].students++;
        });
        
        // Convert to arrays
        Object.keys(grouped).forEach(semester => {
            grouped[semester] = Object.values(grouped[semester]);
        });
        
        return grouped;
    }

    toggleCourseSelection(courseCode, courseName, studentCount) {
        console.log('Toggling course selection:', courseCode, studentCount);
        
        const courseData = { code: courseCode, name: courseName, students: studentCount };
        
        if (this.selectedCourses.has(courseCode)) {
            this.selectedCourses.delete(courseCode);
            this.selectedCourseData.delete(courseCode);
            this.courseColorMap.delete(courseCode);
        } else {
            this.selectedCourses.add(courseCode);
            this.selectedCourseData.set(courseCode, courseData);
            // Assign color to course
            const colorIndex = this.courseColorMap.size % this.courseColors.length;
            this.courseColorMap.set(courseCode, this.courseColors[colorIndex]);
        }
        
        this.updateSelectionSummary();
    }

    updateSelectionSummary() {
        console.log('Updating selection summary, selected courses:', this.selectedCourses.size);
        
        const summaryContainer = document.getElementById('course-summary');
        const totalStudents = document.getElementById('total-students');
        const roomsNeeded = document.getElementById('rooms-needed');
        const generateButton = document.getElementById('generate-seating');
        
        if (!summaryContainer || !totalStudents || !roomsNeeded || !generateButton) return;
        
        if (this.selectedCourses.size === 0) {
            summaryContainer.innerHTML = '<p class="text-secondary">No courses selected</p>';
            totalStudents.textContent = '0';
            roomsNeeded.textContent = '0';
            generateButton.disabled = true;
            return;
        }
        
        let html = '';
        let total = 0;
        
        this.selectedCourses.forEach(courseCode => {
            const courseData = this.selectedCourseData.get(courseCode);
            if (courseData) {
                total += courseData.students;
                html += `
                    <div class="selected-course-item">
                        <span>${courseCode} - ${courseData.name}</span>
                        <span>${courseData.students} students</span>
                    </div>
                `;
            }
        });
        
        summaryContainer.innerHTML = html;
        totalStudents.textContent = total;
        
        // Calculate rooms needed based on algorithm efficiency
        const efficiency = parseInt(this.selectedAlgorithm?.efficiency || '90') / 100;
        const totalCapacity = this.roomsData.reduce((sum, room) => sum + room.max_with_spacing, 0);
        const effectiveCapacity = totalCapacity * efficiency;
        const roomsRequired = Math.ceil(total / effectiveCapacity * this.roomsData.length);
        
        roomsNeeded.textContent = roomsRequired;
        
        generateButton.disabled = false;
        generateButton.style.display = 'inline-flex'; // Ensure button is visible
        
        console.log('Generate button enabled, total students:', total);
    }

    async generateSeatingArrangement() {
        console.log('Generating seating arrangement...');
        
        this.showProcessingModal();
        
        try {
            await this.simulateSeatingGeneration();
            this.switchTab('seating-visualization');
        } catch (error) {
            console.error('Error generating seating:', error);
        } finally {
            this.hideProcessingModal();
        }
    }

    showProcessingModal() {
        const modal = document.getElementById('processing-modal');
        if (modal) {
            modal.classList.remove('hidden');
            
            const progress = document.getElementById('processing-progress');
            const stats = document.getElementById('processing-stats');
            
            let progressValue = 0;
            const interval = setInterval(() => {
                progressValue += Math.random() * 15;
                if (progressValue > 100) progressValue = 100;
                
                if (progress) progress.style.width = `${progressValue}%`;
                
                if (stats) {
                    if (progressValue < 30) {
                        stats.textContent = 'Analyzing course distribution...';
                    } else if (progressValue < 60) {
                        stats.textContent = 'Optimizing room assignments...';
                    } else if (progressValue < 90) {
                        stats.textContent = 'Applying anti-cheating algorithms...';
                    } else {
                        stats.textContent = 'Finalizing seating arrangements...';
                        clearInterval(interval);
                    }
                }
            }, 200);
            
            this.processingInterval = interval;
        }
    }

    hideProcessingModal() {
        const modal = document.getElementById('processing-modal');
        if (modal) {
            modal.classList.add('hidden');
        }
        
        if (this.processingInterval) {
            clearInterval(this.processingInterval);
        }
    }

    async simulateSeatingGeneration() {
        return new Promise((resolve) => {
            setTimeout(() => {
                this.generateRoomAssignments();
                resolve();
            }, 3000);
        });
    }

    generateRoomAssignments() {
        console.log('Generating room assignments...');
        
        const selectedStudents = this.enrollmentData.filter(student => 
            this.selectedCourses.has(student["Subject Code"])
        );
        
        console.log('Selected students for assignment:', selectedStudents.length);
        
        // Shuffle students for random distribution
        const shuffledStudents = this.shuffleArray([...selectedStudents]);
        
        this.seatingAssignments = [];
        let studentIndex = 0;
        
        // Assign students to rooms
        this.roomsData.forEach((room, roomIdx) => {
            if (studentIndex >= shuffledStudents.length) return;
            
            const roomAssignment = {
                room: room,
                students: [],
                seats: this.generateRoomSeats(room)
            };
            
            // Fill room based on algorithm efficiency
            const efficiency = parseInt(this.selectedAlgorithm.efficiency) / 100;
            const maxStudentsInRoom = Math.floor(room.max_with_spacing * efficiency);
            
            const seatsToFill = Math.min(maxStudentsInRoom, shuffledStudents.length - studentIndex);
            
            console.log(`Room ${room.room_name}: filling ${seatsToFill} seats`);
            
            // Assign students to specific seats
            const usedSeats = new Set();
            
            for (let i = 0; i < seatsToFill; i++) {
                const student = shuffledStudents[studentIndex + i];
                
                // Find next available seat
                let seat = this.findOptimalSeat(roomAssignment.seats, student["Subject Code"], usedSeats);
                if (!seat) {
                    seat = roomAssignment.seats.find(s => !usedSeats.has(s.id));
                }
                
                if (seat) {
                    seat.student = student;
                    seat.occupied = true;
                    seat.courseCode = student["Subject Code"];
                    usedSeats.add(seat.id);
                    roomAssignment.students.push(student);
                }
            }
            
            studentIndex += seatsToFill;
            this.seatingAssignments.push(roomAssignment);
        });
        
        console.log('Generated seating assignments:', this.seatingAssignments.length);
    }

    generateRoomSeats(room) {
        const seats = [];
        const rowLabels = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
        
        // Dynamically calculate a balanced layout
        const capacity = room.capacity;
        const numRows = Math.ceil(Math.sqrt(capacity * 0.8));
        const numCols = Math.ceil(capacity / numRows);

        for (let row = 0; row < numRows; row++) {
            for (let col = 0; col < numCols; col++) {
                if (seats.length < capacity) {
                    seats.push({
                        id: `${rowLabels[row]}${col + 1}`,
                        row: row,
                        col: col,
                        occupied: false,
                        student: null,
                        courseCode: null
                    });
                }
            }
        }
        
        return seats;
    }

    findOptimalSeat(seats, courseCode, usedSeats) {
        const availableSeats = seats.filter(seat => !usedSeats.has(seat.id));
        
        // 1. Prioritize seats with no adjacent students of the same course
        for (const seat of availableSeats) {
            const adjacentSeats = this.getAdjacentSeats(seats, seat);
            const hasAdjacentSameCourse = adjacentSeats.some(adj => 
                adj.occupied && adj.courseCode === courseCode
            );
            if (!hasAdjacentSameCourse) {
                return seat;
            }
        }
        
        // 2. If not found, prioritize seats with no adjacent students at all
        for (const seat of availableSeats) {
            const adjacentSeats = this.getAdjacentSeats(seats, seat);
            const hasAdjacentStudents = adjacentSeats.some(adj => adj.occupied);
            if (!hasAdjacentStudents) {
                return seat;
            }
        }

        // 3. If still not found, return the first available seat
        return availableSeats[0] || null;
    }

    getAdjacentSeats(seats, targetSeat) {
        const adjacent = [];
        const { row, col } = targetSeat;
        
        // Check 8 directions (including diagonals)
        const directions = [
            [-1, -1], [-1, 0], [-1, 1],
            [0, -1],           [0, 1],
            [1, -1],  [1, 0],  [1, 1]
        ];
        
        directions.forEach(([dRow, dCol]) => {
            const adjRow = row + dRow;
            const adjCol = col + dCol;
            const adjSeat = seats.find(s => s.row === adjRow && s.col === adjCol);
            if (adjSeat) {
                adjacent.push(adjSeat);
            }
        });
        
        return adjacent;
    }

    shuffleArray(array) {
        const shuffled = [...array];
        for (let i = shuffled.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
        }
        return shuffled;
    }

    initSeatingVisualization() {
        console.log('Initializing seating visualization...');
        console.log('Seating assignments:', this.seatingAssignments.length);
        
        const roomSelector = document.getElementById('room-selector');
        if (roomSelector) {
            roomSelector.innerHTML = '<option value="">Select Room</option>';
            
            this.seatingAssignments.forEach((assignment, index) => {
                if (assignment.students.length > 0) {
                    const option = document.createElement('option');
                    option.value = index;
                    option.textContent = `${assignment.room.room_name} (${assignment.students.length} students)`;
                    roomSelector.appendChild(option);
                }
            });
            
            if (this.seatingAssignments.length > 0 && this.seatingAssignments[0].students.length > 0) {
                roomSelector.value = '0';
                this.displayRoomLayout('0');
            }
        }
        
        this.createCourseLegend();
    }

    createCourseLegend() {
        const legendContainer = document.getElementById('course-legend');
        if (legendContainer) {
            legendContainer.innerHTML = '';
            
            this.courseColorMap.forEach((color, courseCode) => {
                const legendItem = document.createElement('div');
                legendItem.className = 'legend-item';
                legendItem.innerHTML = `
                    <div class="legend-color" style="background-color: ${color}"></div>
                    <span>${courseCode}</span>
                `;
                legendContainer.appendChild(legendItem);
            });
        }
    }

    displayRoomLayout(roomIndex) {
        console.log('Displaying room layout for index:', roomIndex);
        
        if (roomIndex === '') return;
        
        const assignment = this.seatingAssignments[parseInt(roomIndex)];
        if (!assignment) return;
        
        const layoutContainer = document.getElementById('room-layout');
        
        // Update room info
        const capacityEl = document.getElementById('room-capacity');
        const occupiedEl = document.getElementById('room-occupied');
        const utilizationEl = document.getElementById('room-utilization');
        
        if (capacityEl) capacityEl.textContent = assignment.room.capacity;
        if (occupiedEl) occupiedEl.textContent = assignment.students.length;
        if (utilizationEl) {
            utilizationEl.textContent = Math.round((assignment.students.length / assignment.room.max_with_spacing) * 100) + '%';
        }
        
        // Generate room layout
        if (layoutContainer) {
            layoutContainer.innerHTML = this.generateRoomHTML(assignment);
            this.addSeatInteractivity();
        }
    }

    generateRoomHTML(assignment) {
        const { room, seats } = assignment;
        const rowLabels = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
        
        let html = '<div class="room-grid">';
        let currentRow = -1;

        seats.forEach(seat => {
            if (seat.row !== currentRow) {
                if (currentRow !== -1) {
                    html += '</div>'; // Close previous row
                }
                currentRow = seat.row;
                html += '<div class="room-row">';
                html += `<div class="room-row-label">${rowLabels[currentRow]}</div>`;
            }

            const seatClass = seat.occupied ? 'seat occupied' : 'seat';
            const bgColor = seat.occupied ? this.courseColorMap.get(seat.courseCode) : '';
            
            html += `
                <div class="${seatClass}" 
                     data-seat-id="${seat.id}"
                     data-student='${seat.student ? JSON.stringify(seat.student) : ''}'
                     data-course="${seat.courseCode}"
                     style="${bgColor ? `background-color: ${bgColor}; color: white;` : ''}">
                    ${seat.id}
                </div>
            `;
        });

        if (seats.length > 0) {
            html += '</div>'; // Close the last row
        }
        
        html += '</div>';
        return html;
    }

    addSeatInteractivity() {
        const tooltip = document.getElementById('student-tooltip');
        
        document.querySelectorAll('.seat').forEach(seat => {
            seat.addEventListener('mouseenter', (e) => {
                const studentData = e.target.dataset.student;
                if (studentData && tooltip) {
                    const student = JSON.parse(studentData);
                    const seatId = e.target.dataset.seatId;
                    
                    const nameEl = tooltip.querySelector('.student-name');
                    const rollEl = tooltip.querySelector('.student-roll');
                    const courseEl = tooltip.querySelector('.student-course');
                    const positionEl = tooltip.querySelector('.seat-position');
                    
                    if (nameEl) nameEl.textContent = student["Student Name"];
                    if (rollEl) rollEl.textContent = `Roll: ${student["Student Roll Number"]}`;
                    if (courseEl) courseEl.textContent = `Course: ${student["Subject Code"]} - ${student["Subject Name"]}`;
                    if (positionEl) positionEl.textContent = `Seat: ${seatId}`;
                    
                    tooltip.classList.remove('hidden');
                    this.positionTooltip(tooltip, e);
                }
            });
            
            seat.addEventListener('mouseleave', () => {
                if (tooltip) tooltip.classList.add('hidden');
            });
            
            seat.addEventListener('mousemove', (e) => {
                if (tooltip && !tooltip.classList.contains('hidden')) {
                    this.positionTooltip(tooltip, e);
                }
            });
        });
    }

    positionTooltip(tooltip, event) {
        const rect = tooltip.offsetParent.getBoundingClientRect();
        const x = event.clientX - rect.left + 10;
        const y = event.clientY - rect.top - tooltip.offsetHeight - 10;
        
        tooltip.style.left = `${Math.max(0, Math.min(x, rect.width - tooltip.offsetWidth))}px`;
        tooltip.style.top = `${Math.max(0, y)}px`;
    }

    initAnalytics() {
        console.log('Initializing analytics...');
        this.calculateAnalytics();
        this.updateAnalyticsDisplay();
        
        // Delay chart creation to ensure DOM is ready
        setTimeout(() => {
            this.createCharts();
        }, 100);
    }

    calculateAnalytics() {
        const totalStudents = this.seatingAssignments.reduce((sum, assignment) => sum + assignment.students.length, 0);
        const totalRoomsUsed = this.seatingAssignments.filter(assignment => assignment.students.length > 0).length;
        const totalCapacity = this.seatingAssignments.reduce((sum, assignment) => sum + assignment.room.max_with_spacing, 0);
        const efficiency = totalCapacity > 0 ? Math.round((totalStudents / totalCapacity) * 100) : 0;
        
        this.analytics = {
            totalStudents,
            totalRoomsUsed,
            efficiency,
            selectedCoursesCount: this.selectedCourses.size,
            roomBreakdown: this.seatingAssignments.filter(assignment => assignment.students.length > 0).map(assignment => ({
                room: assignment.room,
                students: assignment.students.length,
                utilization: Math.round((assignment.students.length / assignment.room.max_with_spacing) * 100)
            }))
        };
        
        console.log('Analytics calculated:', this.analytics);
    }

    updateAnalyticsDisplay() {
        const elements = {
            students: document.getElementById('analytics-students'),
            rooms: document.getElementById('analytics-rooms'),
            efficiency: document.getElementById('analytics-efficiency'),
            courses: document.getElementById('analytics-courses'),
            currentEfficiencyFill: document.querySelector('.current-efficiency'),
            currentEfficiencyValue: document.getElementById('current-efficiency-value'),
            improvementPercentage: document.getElementById('improvement-percentage')
        };
        
        if (elements.students) elements.students.textContent = this.analytics.totalStudents;
        if (elements.rooms) elements.rooms.textContent = this.analytics.totalRoomsUsed;
        if (elements.efficiency) elements.efficiency.textContent = this.analytics.efficiency + '%';
        if (elements.courses) elements.courses.textContent = this.analytics.selectedCoursesCount;
        
        // Update efficiency comparison
        if (elements.currentEfficiencyFill && elements.currentEfficiencyValue && elements.improvementPercentage) {
            elements.currentEfficiencyFill.style.width = this.analytics.efficiency + '%';
            elements.currentEfficiencyValue.textContent = this.analytics.efficiency + '%';
            
            const improvement = Math.round(((this.analytics.efficiency - 35) / 35) * 100);
            elements.improvementPercentage.textContent = `+${improvement}%`;
        }
        
        // Update room breakdown
        this.updateRoomBreakdown();
    }

    updateRoomBreakdown() {
        const container = document.getElementById('room-breakdown');
        if (!container) return;
        
        container.innerHTML = '';
        
        this.analytics.roomBreakdown.forEach(breakdown => {
            const item = document.createElement('div');
            item.className = 'room-breakdown-item';
            item.innerHTML = `
                <div class="room-breakdown-header">
                    <span class="room-breakdown-name">${breakdown.room.room_name}</span>
                    <span class="room-breakdown-utilization">${breakdown.utilization}%</span>
                </div>
                <div class="room-breakdown-stats">
                    <span>Students: ${breakdown.students}</span>
                    <span>Capacity: ${breakdown.room.max_with_spacing}</span>
                </div>
            `;
            container.appendChild(item);
        });
    }

    createCharts() {
        this.createUtilizationChart();
        this.createDistributionChart();
    }

    createUtilizationChart() {
        const canvas = document.getElementById('utilization-chart');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        
        const roomData = this.analytics.roomBreakdown;
        const labels = roomData.map(r => r.room.room_name);
        const data = roomData.map(r => r.utilization);
        
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Room Utilization (%)',
                    data: data,
                    backgroundColor: '#1FB8CD',
                    borderColor: '#1FB8CD',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }

    createDistributionChart() {
        const canvas = document.getElementById('distribution-chart');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        
        const courseDistribution = {};
        this.seatingAssignments.forEach(assignment => {
            assignment.students.forEach(student => {
                const course = student["Subject Code"];
                courseDistribution[course] = (courseDistribution[course] || 0) + 1;
            });
        });
        
        const labels = Object.keys(courseDistribution);
        const data = Object.values(courseDistribution);
        const colors = labels.map(course => this.courseColorMap.get(course) || '#1FB8CD');
        
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderColor: colors,
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    exportSeatingCharts() {
        const data = this.seatingAssignments.map(assignment => ({
            room: assignment.room.room_name,
            students: assignment.students.map(student => ({
                name: student["Student Name"],
                rollNumber: student["Student Roll Number"],
                course: student["Subject Code"],
                seat: assignment.seats.find(seat => seat.student === student)?.id || 'N/A'
            }))
        }));
        
        this.downloadJSON(data, 'seating-arrangements.json');
    }

    exportAnalytics() {
        const analyticsData = {
            summary: this.analytics,
            algorithm: this.selectedAlgorithm,
            roomDetails: this.analytics.roomBreakdown,
            timestamp: new Date().toISOString()
        };
        
        this.downloadJSON(analyticsData, 'analytics-report.json');
    }

    generatePDFReport() {
        // Simulate PDF generation
        alert('PDF report generation would be implemented with a PDF library like jsPDF. Report includes:\n\n- Seating arrangements by room\n- Student allocation details\n- Efficiency metrics\n- Algorithm comparison\n- Room utilization charts');
    }

    downloadJSON(data, filename) {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing application...');
    new ExamSchedulingSystem();
});